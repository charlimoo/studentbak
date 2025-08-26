# apps/applications/signals.py
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Application, ApplicationLog, ApplicationTask

def process_final_application_decision(application):
    """
    Business logic to determine the final status of an application.
    RULE: Approved if AT LEAST ONE university approves. Rejected only if ALL reject.
    """
    all_tasks = application.tasks.all()
    if not all_tasks:
        return

    # Check if all tasks for this application are now completed.
    if all(task.status == ApplicationTask.StatusChoices.COMPLETED for task in all_tasks):
        
        # Prevent this logic from running again if a final decision has already been made.
        if application.status not in [Application.StatusChoices.APPROVED, Application.StatusChoices.REJECTED]:
            
            has_at_least_one_approval = any(
                task.decision == ApplicationTask.DecisionChoices.APPROVED for task in all_tasks
            )

            if has_at_least_one_approval:
                final_status = Application.StatusChoices.APPROVED
                log_action = "Final decision reached: Approved."
            else:
                final_status = Application.StatusChoices.REJECTED
                log_action = "Final decision reached: Rejected."

            # Update the application status and create a system-generated log entry.
            application.status = final_status
            application.save(update_fields=['status'])
            
            ApplicationLog.objects.create(
                application=application,
                actor=None,  # System action
                action=log_action
            )

@receiver(post_save, sender=ApplicationTask)
def on_application_task_save(sender, instance, created, **kwargs):
    """
    Signal receiver that triggers after an ApplicationTask is saved.
    Checks if a final decision can now be made on the parent application.
    """
    task = instance
    if task.status == ApplicationTask.StatusChoices.COMPLETED:
        # Using transaction.on_commit ensures this runs only after the
        # database transaction that saved the task has successfully completed.
        transaction.on_commit(lambda: process_final_application_decision(task.application))
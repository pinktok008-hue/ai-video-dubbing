"""
Task Manager
-----------------
Version : 2.0

Responsible for:

• Create Task
• Update Status
• Store Progress
• Store Current Stage
• ETA
• Elapsed Time
• Download URL
"""

from uuid import uuid4
from datetime import datetime
from threading import Lock


class TaskManager:

    def __init__(self):

        self.tasks = {}

        self.lock = Lock()

    # -----------------------------

    def create_task(self):

        task_id = str(uuid4())

        with self.lock:

            self.tasks[task_id] = {

                "task_id": task_id,

                "status": "waiting",

                "stage": "Waiting",

                "progress": 0,

                "message": "Waiting to start",

                "created_at": datetime.utcnow(),

                "started_at": None,

                "completed_at": None,

                "elapsed_time": 0,

                "eta": None,

                "download_url": None,

                "error": None

            }

        return task_id

    # -----------------------------

    def start_task(self, task_id):

        if task_id not in self.tasks:
            return

        self.tasks[task_id]["status"] = "processing"

        self.tasks[task_id]["started_at"] = datetime.utcnow()

    # -----------------------------

    def update_progress(

            self,

            task_id,

            progress,

            stage,

            message

    ):

        if task_id not in self.tasks:
            return

        progress = max(0, min(100, progress))

        self.tasks[task_id]["progress"] = progress

        self.tasks[task_id]["stage"] = stage

        self.tasks[task_id]["message"] = message

        if self.tasks[task_id]["started_at"]:

            elapsed = (

                datetime.utcnow()

                -

                self.tasks[task_id]["started_at"]

            ).total_seconds()

            self.tasks[task_id]["elapsed_time"] = round(elapsed)

    # -----------------------------

    def complete_task(

            self,

            task_id,

            download_url

    ):

        if task_id not in self.tasks:
            return

        self.tasks[task_id]["status"] = "completed"

        self.tasks[task_id]["progress"] = 100

        self.tasks[task_id]["stage"] = "Completed"

        self.tasks[task_id]["message"] = "Video Ready"

        self.tasks[task_id]["download_url"] = download_url

        self.tasks[task_id]["completed_at"] = datetime.utcnow()

    # -----------------------------

    def fail_task(

            self,

            task_id,

            error

    ):

        if task_id not in self.tasks:
            return

        self.tasks[task_id]["status"] = "failed"

        self.tasks[task_id]["error"] = str(error)

    # -----------------------------

    def get_task(

            self,

            task_id

    ):

        return self.tasks.get(task_id)

    # -----------------------------

    def delete_task(

            self,

            task_id

    ):

        if task_id in self.tasks:

            del self.tasks[task_id]

    # -----------------------------

    def all_tasks(self):

        return self.tasks


task_manager = TaskManager()

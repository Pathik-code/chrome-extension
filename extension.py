from plyer import notification
import pygame
from datetime import datetime, time, timedelta
import json
import threading
import time as tm
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import warnings

# Get the current directory and initialize pygame
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
NOTIFICATION_SOUNDS_DIR = os.path.join(CURRENT_DIR, 'notification_sounds')

# Initialize pygame mixer
pygame.mixer.init()

# Load all sound files from the notification_sounds directory
SOUND_FILES = {os.path.splitext(file)[0]: file for file in os.listdir(NOTIFICATION_SOUNDS_DIR) if file.endswith('.mp3')}

class Task:
    def __init__(self, name, start_time, end_time, subtasks=None):
        self.name = name
        self.start_time = start_time
        self.end_time = end_time
        self.subtasks = subtasks if subtasks else []

class ScheduleManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.schedules_dir = os.path.join(base_dir, 'schedules')
        os.makedirs(self.schedules_dir, exist_ok=True)

    def get_schedule_path(self, date_str):
        return os.path.join(self.schedules_dir, f'{date_str}.json')

    def save_schedule(self, schedule, date_str):
        file_path = self.get_schedule_path(date_str)
        with open(file_path, 'w') as f:
            json.dump(schedule, f, indent=4)

    def load_schedule(self, date_str):
        file_path = self.get_schedule_path(date_str)
        try:
            with open(file_path, 'r') as f:
                print(f"Loading schedule from {file_path}")
                return json.load(f)
        except FileNotFoundError:
            print(f"No schedule found for date {date_str}")
            return {}

    def get_available_dates(self):
        dates = []
        for file in os.listdir(self.schedules_dir):
            if file.endswith('.json'):
                date_str = file[:-5]  # Extract date from filename
                dates.append(date_str)
        return sorted(dates)

def play_notification_sound(sound_type='default', volume=0.5):
    try:
        sound_file = os.path.join(NOTIFICATION_SOUNDS_DIR, SOUND_FILES[0].get(sound_type, SOUND_FILES.get('default')))
        if not os.path.exists(sound_file):
            raise FileNotFoundError(f"Sound file '{sound_file}' not found.")
        pygame.mixer.music.load(sound_file)
        pygame.mixer.music.set_volume(volume / 100)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            tm.sleep(0.1)
    except Exception as e:
        print(f"Sound playback error: {e}")

def create_notification(title, message, sound_type='default', volume=0.5):
    try:
        notification.notify(
            title=title,
            message=message,
            app_icon=None,
            timeout=10,
        )
        # Start sound in a separate thread
        sound_thread = threading.Thread(target=play_notification_sound, args=(sound_type, volume))
        sound_thread.daemon = True
        sound_thread.start()
    except Exception as e:
        print(f"Notification error: {e}")

# Initialize Flask app
app = Flask(__name__)
app.config['DEBUG'] = True
CORS(app, resources={
    r"/*": {
        "origins": ["chrome-extension://*", "http://localhost:*"],
        "methods": ["GET", "POST", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True
    }
})

# Initialize schedule manager
schedule_manager = ScheduleManager(CURRENT_DIR)

def create_today_schedule():
    today_date_str = datetime.now().strftime('%Y-%m-%d')
    schedule_path = schedule_manager.get_schedule_path(today_date_str)
    if not os.path.exists(schedule_path):
        default_schedule = schedule_manager.load_schedule(today_date_str)
        schedule_manager.save_schedule(default_schedule, today_date_str)

# Initialize schedule manager and create today's schedule if it doesn't exist
schedule_manager = ScheduleManager(CURRENT_DIR)
create_today_schedule()

@app.route('/schedule/<date>')
def get_schedule_by_date(date):
    try:
        schedule = schedule_manager.load_schedule(date)
        return jsonify(schedule)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def check_time_conflict(schedule, start_time, end_time):
    """
    Check if the given start_time and end_time conflict with any existing tasks in the schedule.
    :param schedule: The schedule to check against.
    :param start_time: The start time of the new task.
    :param end_time: The end time of the new task.
    :return: (conflict, task_name) - conflict is True if there is a conflict, False otherwise.
             task_name is the name of the conflicting task if there is a conflict.
    """
    new_start = datetime.strptime(start_time, "%H:%M").time()
    new_end = datetime.strptime(end_time, "%H:%M").time()

    for task_id, task in schedule.items():
        existing_start = datetime.strptime(task['start_time'], "%H:%M").time()
        existing_end = datetime.strptime(task['end_time'], "%H:%M").time()

        if (new_start < existing_end and new_end > existing_start):
            return True, task['name']

    return False, None

@app.route('/schedule/copy', methods=['POST'])
def copy_schedule():
    try:
        source_date = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        target_date = datetime.now().strftime('%Y-%m-%d')

        # Load source schedule (yesterday's schedule)
        source_schedule = schedule_manager.load_schedule(source_date)
        if not source_schedule:
            return jsonify({
                "status": "error",
                "message": f"No schedule found for date {source_date}"
            }), 404

        # Load target schedule (today's schedule) if it exists
        target_schedule = schedule_manager.load_schedule(target_date)

        # Check for time conflicts if target schedule exists
        if target_schedule:
            for task_id, task in source_schedule.items():
                conflict, task_name = check_time_conflict(
                    target_schedule,
                    task['start_time'],
                    task['end_time']
                )
                if conflict:
                    return jsonify({
                        "status": "error",
                        "message": f"Time conflict with task: {task_name}"
                    }), 400

        # Create new schedule with updated task IDs
        new_schedule = {}
        for i, (_, task) in enumerate(source_schedule.items(), 1):
            new_task_id = f"{target_date}_{i:03d}"
            new_schedule[new_task_id] = {
                "name": task['name'],
                "start_time": task['start_time'],
                "end_time": task['end_time'],
                "subtasks": task['subtasks']
            }

        # Merge new schedule with existing target schedule if it exists
        if target_schedule:
            merged_schedule = {**target_schedule, **new_schedule}
            schedule_manager.save_schedule(merged_schedule, target_date)
            message = "Schedule copied and appended successfully"
        else:
            schedule_manager.save_schedule(new_schedule, target_date)
            message = "Schedule copied successfully"

        print(f"Successfully copied schedule from {source_date} to {target_date}")
        return jsonify({
            "status": "success",
            "message": message
        })

    except Exception as e:
        print(f"Error copying schedule: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error copying schedule: {str(e)}"
        }), 500

@app.route('/schedule/available_dates')
def get_available_dates():
    try:
        dates = schedule_manager.get_available_dates()
        return jsonify({"dates": dates})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/add_task', methods=['POST'])
def add_task():
    try:
        task_data = request.json
        date_str = task_data.get('date', datetime.now().strftime('%Y-%m-%d'))

        # Ensure the schedules directory exists
        os.makedirs(schedule_manager.schedules_dir, exist_ok=True)

        # Load or create the schedule for the specified date
        schedule = schedule_manager.load_schedule(date_str)
        if not schedule:
            schedule = {}

        # Check for time conflicts
        conflict, task_name = check_time_conflict(
            schedule,
            task_data['start_time'],
            task_data['end_time']
        )

        if conflict:
            return jsonify({
                "error": f"Time conflict with task: {task_name}"
            }), 400

        # Determine the highest existing task ID
        max_id = 0
        for task_id in schedule.keys():
            try:
                task_num = int(task_id.split('_')[1])
                if task_num > max_id:
                    max_id = task_num
            except (IndexError, ValueError):
                continue

        # Add task with notification settings
        new_task_id = f"{date_str}_{max_id + 1:03d}"
        new_task = {
            "name": task_data['name'],
            "start_time": task_data['start_time'],
            "end_time": task_data['end_time'],
            "subtasks": task_data['subtasks']
        }

        schedule[new_task_id] = new_task
        schedule_manager.save_schedule(schedule, date_str)

        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/delete_task/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    try:
        # Extract date from task_id
        date_str = task_id.split('_')[0]
        schedule = schedule_manager.load_schedule(date_str)

        if task_id not in schedule:
            return jsonify({
                "error": f"Task '{task_id}' not found",
                "available_tasks": list(schedule.keys())
            }), 404

        # if not task_id.startswith('Custom Task'):
        #     return jsonify({
        #         "error": "Cannot delete default tasks",
        #         "task_type": "default"
        #     }), 403

        deleted_task = schedule[task_id]
        del schedule[task_id]

        schedule_manager.save_schedule(schedule, date_str)

        return jsonify({
            "status": "success",
            "message": f"Task {task_id} deleted successfully",
            "deleted_task": deleted_task
        }), 200

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500

def check_reminders(notification_gap=5):
    while True:
        current_time = datetime.now()
        current_date = current_time.strftime('%Y-%m-%d')
        current_schedule = schedule_manager.load_schedule(current_date)

        for period, task in current_schedule.items():
            task_time = datetime.strptime(task["start_time"], "%H:%M").time()
            end_time = datetime.strptime(task["end_time"], "%H:%M").time()
            notification_settings = task.get('notification', {})

            if notification_settings.get('enabled', True):
                reminder_time = notification_settings.get('reminder_time', notification_gap)
                check_start_time = (datetime.combine(datetime.today(), task_time) -
                                    timedelta(minutes=reminder_time)).time()
                check_end_time = (datetime.combine(datetime.today(), end_time) -
                                  timedelta(minutes=reminder_time)).time()

                if current_time.time().strftime("%H:%M") == check_start_time.strftime("%H:%M"):
                    message = f"Task '{task['name']}' will start in {reminder_time} minutes.\nSubtasks:\n" + \
                              "\n".join(f"- {st}" for st in task["subtasks"])
                    create_notification(
                        f"Upcoming Task - {period}",
                        message,
                        notification_settings.get('sound_type', 'default'),
                        notification_settings.get('volume', 50)
                    )

                if current_time.time().strftime("%H:%M") == check_end_time.strftime("%H:%M"):
                    message = f"Task '{task['name']}' will end in {reminder_time} minutes.\nSubtasks:\n" + \
                              "\n".join(f"- {st}" for st in task["subtasks"])
                    create_notification(
                        f"Ending Task - {period}",
                        message,
                        notification_settings.get('sound_type', 'default'),
                        notification_settings.get('volume', 50)
                    )

        tm.sleep(60)

# Add OPTIONS handler for all routes
@app.route('/', methods=['OPTIONS'])
@app.route('/schedule', methods=['OPTIONS'])
@app.route('/add_task', methods=['OPTIONS'])
@app.route('/delete_task/<task_id>', methods=['OPTIONS'])
def handle_options():
    return '', 204

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "endpoints": {
            "/schedule": "Get the current schedule",
            "/schedule/<date>": "Get schedule by date",
            "/schedule/copy": "Copy schedule to another date",
            "/schedule/available_dates": "Get available schedule dates",
            "/health": "Check server health"
        }
    })

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"})

@app.route('/schedule')
def get_schedule():
    try:
        schedule = schedule_manager.load_schedule(datetime.now().strftime('%Y-%m-%d'))
        print(schedule)
        return jsonify(schedule)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def run_flask():
    try:
        app.run(port=5000, host='0.0.0.0', use_reloader=False)  # Disable reloader
    except Exception as e:
        print(f"Flask server error: {e}")

def main():
    try:
        # Start the Flask server in a separate thread
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()

        # Start the reminder checking thread
        reminder_thread = threading.Thread(target=check_reminders)
        reminder_thread.daemon = True
        reminder_thread.start()

        # Keep the main thread alive
        while True:
            tm.sleep(1)
    except Exception as e:
        print(f"Main thread error: {e}")

if __name__ == "__main__":
    main()

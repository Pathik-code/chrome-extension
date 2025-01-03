document.addEventListener('DOMContentLoaded', function() {
    const scheduleDiv = document.getElementById('schedule');
    const taskForm = document.getElementById('taskForm');

    // Schedule type handling
    const scheduleType = document.getElementById('scheduleType');
    const dateSelector = document.getElementById('dateSelector');
    const copyControls = document.getElementById('copyControls');
    const scheduleDate = document.getElementById('scheduleDate');

    scheduleType.addEventListener('change', function() {
        dateSelector.style.display = this.value === 'custom' ? 'block' : 'none';
        copyControls.style.display = this.value === 'copy' ? 'flex' : 'none';
        if (this.value === 'today') {
            fetchSchedule('today');
        }
    });

    scheduleDate.addEventListener('change', function() {
        fetchSchedule(this.value);
    });

    // Alarm settings handling
    const enableAlarm = document.getElementById('enableAlarm');
    const notificationSettings = document.getElementById('notificationSettings');
    const volume = document.getElementById('volume');

    enableAlarm.addEventListener('change', function() {
        notificationSettings.style.display = this.checked ? 'block' : 'none';
        chrome.storage.local.set({ alarmEnabled: this.checked });
    });

    volume.addEventListener('change', function() {
        chrome.storage.local.set({ volume: this.value });
    });

    async function fetchSchedule(date = 'today') {
        scheduleDiv.innerHTML = 'Loading...';
        const url = date === 'today'
            ? 'http://localhost:5000/schedule'
            : `http://localhost:5000/schedule/${date}`;

        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const schedule = await response.json();
            displaySchedule(schedule, date);
        } catch (error) {
            scheduleDiv.innerHTML = `<div class="error">Error loading schedule: ${error.message}</div>`;
        }
    }

    async function fetchPreviousSchedule() {
        try {
            const response = await fetch('http://localhost:5000/schedule/available_dates');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const { dates } = await response.json();
            // Display schedule selection dialog
            // ... implementation
        } catch (error) {
            alert('Error loading previous schedules: ' + error.message);
        }
    }

    function displaySchedule(schedule, date) {
        scheduleDiv.innerHTML = '';

        // Add date header
        const dateHeader = document.createElement('h2');
        dateHeader.textContent = `Tasks for ${date === 'today' ? 'Today' : date}`;
        scheduleDiv.appendChild(dateHeader);

        for (const [period, task] of Object.entries(schedule)) {
            scheduleDiv.innerHTML += `
                <div class="task" data-task-id="${period}">
                    <div class="task-header">
                        <h3>${task.name}</h3>
                        <button class="delete-btn" data-task-id="${period}">Delete</button>
                    </div>
                    <p>${task.start_time} - ${task.end_time}</p>
                    <div class="subtasks">
                        ${task.subtasks.map(st => `<p>• ${st}</p>`).join('')}
                    </div>
                    <p class="task-date">Task Date: ${date === 'today' ? 'Today' : date}</p>
                </div>
            `;
        }

        // Add event listeners to delete buttons
        document.querySelectorAll('.delete-btn').forEach(button => {
            button.addEventListener('click', async function() {
                const taskId = this.getAttribute('data-task-id');
                await deleteTask(taskId, date);
            });
        });
    }

    // Initial fetch
    fetchSchedule();

    // Add Task button handler
    document.getElementById('addTask').addEventListener('click', () => {
        taskForm.style.display = 'block';
    });

    // Cancel button handler
    document.getElementById('cancelTask').addEventListener('click', () => {
        taskForm.style.display = 'none';
        clearForm();
    });

    // Save Task button handler
    document.getElementById('saveTask').addEventListener('click', async () => {
        const taskData = {
            name: document.getElementById('taskName').value,
            date: document.getElementById('taskDate').value,
            start_time: document.getElementById('startTime').value,
            end_time: document.getElementById('endTime').value,
            subtasks: document.getElementById('subtasks').value
                .split('\n')
                .filter(task => task.trim() !== ''),
            notification: {
                enabled: document.getElementById('setAlarm').checked,
                sound_type: document.getElementById('notificationSound').value,
                volume: document.getElementById('volume').value,
                reminder_time: document.getElementById('reminderTime').value
            }
        };

        try {
            const response = await fetch('http://localhost:5000/add_task', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(taskData)
            });

            if (!response.ok) {
                throw new Error('Failed to add task');
            }

            taskForm.style.display = 'none';
            clearForm();
            fetchSchedule(taskData.date);  // Fetch the schedule for the specified date
        } catch (error) {
            alert('Error adding task: ' + error.message);
        }
    });

    function clearForm() {
        document.getElementById('taskName').value = '';
        document.getElementById('taskDate').value = '';
        document.getElementById('startTime').value = '';
        document.getElementById('endTime').value = '';
        document.getElementById('subtasks').value = '';
    }

    // Refresh button handler
    document.getElementById('refresh').addEventListener('click', () => {
        fetchSchedule();
        chrome.runtime.sendMessage({action: 'refreshSchedule'});
    });

    // Add deleteTask function to window scope
    async function deleteTask(taskId, date) {
        if (!confirm('Are you sure you want to delete this task?')) return;

        try {
            console.log('Deleting task:', taskId);
            const url = `http://localhost:5000/delete_task/${encodeURIComponent(taskId)}`;

            const response = await fetch(url, {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                mode: 'cors'
            });

            console.log('Response headers:', Object.fromEntries(response.headers));

            let data;
            try {
                data = await response.json();
            } catch (parseError) {
                console.error('JSON parse error:', parseError);
                throw new Error('Invalid response format from server');
            }

            if (!response.ok) {
                throw new Error(data.error || `Server returned ${response.status}`);
            }

            console.log('Delete success:', data.message);
            fetchSchedule(date);
        } catch (error) {
            console.error('Delete error:', error);
            alert(`Error deleting task: ${error.message}`);
        }
    }

    // Add copy schedule functionality
    document.getElementById('copyButton').addEventListener('click', async function() {
        const today = new Date().toLocaleDateString('en-GB').split('/').join('-');
        const yesterday = new Date(Date.now() - 86400000).toLocaleDateString('en-GB').split('/').join('-');

        try {
            const response = await fetch('http://localhost:5000/schedule/copy', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    source_date: yesterday,
                    target_date: today
                })
            });

            const data = await response.json();
            if (data.status === 'success') {

                const notification = document.createElement('div');
                notification.className = 'notification success';
                notification.textContent = 'Schedule copied successfully';
                document.getElementById('schedule').insertAdjacentElement('afterbegin', notification);
                setTimeout(() => notification.remove(), 3000);
                fetchSchedule(); // Refresh the schedule
            } else {
                throw new Error(data.error || 'Failed to copy schedule');
            }
        } catch (error) {
            const notification = document.createElement('div');
            notification.className = 'notification error';
            notification.textContent = error.message;
            document.getElementById('schedule').insertAdjacentElement('afterbegin', notification);
            setTimeout(() => notification.remove(), 3000);
        }
    });

    // Initialize settings
    chrome.storage.local.get(['alarmEnabled', 'volume'], function(result) {
        enableAlarm.checked = result.alarmEnabled || false;
        notificationSettings.style.display = result.alarmEnabled ? 'block' : 'none';
        volume.value = result.volume || 50;
    });
});

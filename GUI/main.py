import tkinter as tk
from tkinter import ttk, messagebox
import serial
import json
import smtplib
import threading
import serial.tools.list_ports
from email.mime.text import MIMEText
import os
from datetime import datetime
import requests
import threading

DEBUG_PRINT_INPUT = False
webhook_url = "YOUR_WEBHOOK_URL_HERE"
last_email_times = {i: datetime.min for i in range(16)}

def read_serial():
    try:
        ser_data = ser.readline().decode('utf-8').strip()
        if DEBUG_PRINT_INPUT:
            print("Raw Data:", ser_data)  # Debugging line to check raw serial data
        
        # Handling malformed JSON
        if ser_data.endswith(',\"\"}'):
            ser_data = ser_data[:-4] + '}'
        
        update_gui(json.loads(ser_data))
    except json.JSONDecodeError:
        print("Failed to decode JSON. Received:", ser_data)
    except serial.SerialTimeoutException:
        print("Read timeout - No data received.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to read serial data: {str(e)}")

def update_gui(data):
    global last_email_times  # Ensure we use the global variable
    try:
        # Record the refresh time when data is received
        last_refreshed_time.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        # Initialize all labels to disabled state
        for i, label in enumerate(labels):
            if not probes_var[i].get():
                continue
            else:
                label.config(text=f"Probe {i + 1}: Disabled")

        # Update labels for received data
        for key, temp_str in data.items():
            i = int(key)  # Convert key to zero-based index
            temp = float(temp_str)  # Convert string to float

            if probes_var[i].get():  # Check if the probe is enabled
                labels[i].config(text=f"Probe {i + 1}: {temp}°C")
                
                # Check the condition for sending an email
                if temp > max_temp_var.get() and send_emails.get():
                    # Get the current time
                    now = datetime.now()
                    
                    # Calculate time delta since last email
                    delta = now - last_email_times[i]
                    
                    # Check if it's been more than 5 minutes
                    if delta.total_seconds() >= 300:  # 5 minutes = 300 seconds
                        # Update the last email time for this probe
                        last_email_times[i] = now
                        
                        # Start a new thread to send the email
                        send_email_thread = threading.Thread(
                            target=send_email,
                            args=(
                                "Temperature Alert",
                                f"Probe {i + 1} has reached {temp}°C",
                            ),
                        )
                        send_email_thread.start()
                        
        root.after(1000, read_serial)  # schedule the function to be called after 1s
    except ValueError:
        messagebox.showerror("Error", "Received an invalid temperature reading.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to update GUI: {str(e)}")

import requests

def send_webhook(data):
    try:
        payload = {
            "username": "My Bot",
            "embeds": [
                {
                    "title": "Sensor Data",
                    "description": "Received new sensor data.",
                    "color": 16711680,
                    "fields": []
                }
            ]
        }

        for key, value in data.items():            
            try:
                name_str = f"{int(key) + 1}:" if key.isdigit() else f"{key}:"
            except ValueError as ve:
                print(f"Value error: {ve}")
                name_str = f"{key}:"
                
            field = {
                "name": name_str,
                "value": f"{value}",
                "inline": True
            }
            payload["embeds"][0]["fields"].append(field)

        headers = {'Content-Type': 'application/json'}
        response = requests.post(webhook_url, json=payload, headers=headers)
        
        if response.status_code == 204:
            if DEBUG_PRINT_INPUT:
                print("Webhook sent successfully.")
        else:
            print(f"Failed to send webhook. Status Code: {response.status_code}")
    except Exception as e:
        print(f"Error sending webhook: {str(e)}")


def repeat_send_webhook():
    try:
        ser_data = ser.readline().decode('utf-8').strip()
        
        # Handling malformed JSON
        if ser_data.endswith(',\"\"}'):
            ser_data = ser_data[:-4] + '}'
        
        data = json.loads(ser_data)
        send_webhook(data)
        
        # Setting up the next webhook to be sent in 1 hour
        threading.Timer(3600, repeat_send_webhook).start()
    except json.JSONDecodeError:
        print("Failed to decode JSON. Received:", ser_data)
    except serial.SerialTimeoutException:
        print("Read timeout - No data received.")
    except Exception as e:
        print(f"Failed to read serial data: {str(e)}")

def send_email(subject, body):
    try:
        sender_email = "your_email@gmail.com"
        password = "your_password"
        recipient_emails = list(email_listbox.get(0, tk.END))
    
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ", ".join(recipient_emails)
    
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, recipient_emails, msg.as_string())
        server.quit()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to send email: {str(e)}")

def connect_serial():
    global ser
    try:
        ser = serial.Serial(port_combobox.get(), 9600)
        connect_button.config(state=tk.DISABLED)
        port_combobox.config(state=tk.DISABLED)
        read_serial()
        repeat_send_webhook()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to connect to serial port: {str(e)}")

def toggle_serial_connection():
    if connect_button["text"] == "Connect":
        try:
            global ser
            ser = serial.Serial(port_combobox.get(), 9600)
            connect_button.config(text="Disconnect")
            port_combobox.config(state=tk.DISABLED)
            read_serial()
            repeat_send_webhook()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to connect to serial port: {str(e)}")
    else:
        disconnect_serial()

def disconnect_serial():
    try:
        ser.close()
        connect_button.config(text="Connect")
        port_combobox.config(state=tk.NORMAL)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disconnect serial port: {str(e)}")

def send_serial_config():
    rr = refresh_rate_var.get()*1000
    if rr < 1000:
        messagebox.showerror("Error", "Refresh rate must be at least 1 second")
        return
    probe_data = {f"{i}": probes_var[i].get() for i in range(16)}
    config = {"rr": rr, **probe_data}
    json_config = json.dumps(config)
    
    print("Sending JSON config to Arduino:", json_config)  # Debug print
    
    if ser.is_open:  # Check if the serial connection is open
        try:
            ser.write((json_config + '\n').encode('utf-8'))  # Send json with newline as delimiter
            ser.flush()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to send data: {str(e)}")
    else:
        messagebox.showerror("Error", "Serial port is not open")


def add_email():
    email = email_entry.get()
    if email and email not in email_listbox.get(0, tk.END):
        email_listbox.insert(tk.END, email)
        save_emails()
    email_entry.delete(0, tk.END)

def remove_email(evt):
    idx = email_listbox.curselection()
    if idx:
        email_listbox.delete(idx)
        save_emails()

def save_emails():
    with open("emails.json", "w") as file:
        json.dump(list(email_listbox.get(0, tk.END)), file)

def load_emails():
    if os.path.exists("emails.json"):
        with open("emails.json", "r") as file:
            emails = json.load(file)
            for email in emails:
                email_listbox.insert(tk.END, email)

def send_test_email():
    try:
        send_email("Test Email", "This is a test email from your Temperature Monitoring System.")
        messagebox.showinfo("Success", "Test email sent successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to send test email: {str(e)}")

# GUI
root = tk.Tk()
root.title("Temperature Monitoring")

# Variables
max_temp_var = tk.DoubleVar(value=40.0)
email_var = tk.StringVar(value="recipient1@gmail.com, recipient2@gmail.com")
refresh_rate_var = tk.IntVar(value=2)
probes_var = [tk.BooleanVar(value=True) for _ in range(16)]
send_emails = tk.BooleanVar(value=False)
last_refreshed_time = tk.StringVar(value="Last Refreshed: Never")

# Serial Port Frame
serial_frame = ttk.Frame(root)
serial_frame.grid(row=0, column=0, padx=20, pady=5, sticky=tk.EW)
serial_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand

# Serial Port Label and Combobox
ttk.Label(serial_frame, text="Select Serial Port:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
port_combobox = ttk.Combobox(serial_frame, values=[comport.device for comport in serial.tools.list_ports.comports()])
port_combobox.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
if port_combobox['values']:
    port_combobox.current(0)
else:
    messagebox.showerror("Error", "No serial ports found")

# Connect Button
connect_button = ttk.Button(serial_frame, text="Connect", command=toggle_serial_connection)
connect_button.grid(row=0, column=2, padx=5, pady=5)

# Email Frame
email_frame = ttk.Frame(root)
email_frame.grid(row=1, column=0, padx=20, pady=5, sticky=tk.EW)
email_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand

# Add Email Controls
ttk.Label(email_frame, text="Add Email:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
email_entry = ttk.Entry(email_frame)
email_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
email_add_button = ttk.Button(email_frame, text="Add", command=add_email)
email_add_button.grid(row=0, column=2, padx=5, pady=5)

# Test Email Button
email_test_button = ttk.Button(email_frame, text="Send Test Email", command=send_test_email)
email_test_button.grid(row=0, column=3, padx=5, pady=5)

# Email Listbox
email_listbox = tk.Listbox(root, selectmode=tk.SINGLE, height=5)
email_listbox.grid(row=2, column=0, padx=20, pady=5, sticky=tk.EW)
email_listbox.bind("<Double-Button-1>", remove_email)

# Load email recipients from file
load_emails()

# Label to display the last refreshed timestamp
last_refreshed_label = ttk.Label(root, textvariable=last_refreshed_time)
last_refreshed_label.grid(row=7, column=0, padx=20, pady=5, sticky=tk.W)

# Temperature Display and Control Frame
temp_frame = ttk.Frame(root)
temp_frame.grid(row=3, column=0, padx=20, pady=5, sticky=tk.W)
labels = [ttk.Label(temp_frame, text=f"Probe {i+1}: --°C") for i in range(16)]
for i, (label, var) in enumerate(zip(labels, probes_var)):
    label.grid(row=i, column=0, padx=20, pady=2, sticky=tk.W)
    ttk.Checkbutton(temp_frame, text=f"Enable Probe {i + 1}", variable=var).grid(row=i, column=1, padx=20, pady=2, sticky=tk.W)

# Max Temp Controls Frame
control_frame = ttk.Frame(root)
control_frame.grid(row=4, column=0, padx=20, pady=5, sticky=tk.EW)
control_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand

ttk.Label(control_frame, text="Max Temp (°C):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
max_temp_entry = ttk.Entry(control_frame, textvariable=max_temp_var)
max_temp_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

# Start Sending Emails Button
def toggle_send_emails():
    send_emails.set(not send_emails.get())
    email_button.config(text="Stop Sending Emails" if send_emails.get() else "Start Sending Emails")
    
email_button = ttk.Button(control_frame, text="Start Sending Emails", command=toggle_send_emails)
email_button.grid(row=0, column=2, padx=5, pady=5, sticky=tk.EW)

# Refresh Rate Control Frame
refresh_frame = ttk.Frame(root)
refresh_frame.grid(row=5, column=0, padx=20, pady=5, sticky=tk.EW)
refresh_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand

ttk.Label(refresh_frame, text="Refresh Rate (s):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
refresh_rate_entry = ttk.Entry(refresh_frame, textvariable=refresh_rate_var)
refresh_rate_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

# Send Configuration Button
send_config_button = ttk.Button(root, text="Send Config to Arduino", command=send_serial_config)
send_config_button.grid(row=6, column=0, padx=20, pady=5)

root.columnconfigure(0, weight=1)  # Allow column 0 to expand
root.mainloop()

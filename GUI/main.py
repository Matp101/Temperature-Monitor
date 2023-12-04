import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import serial
import json
import smtplib
import threading
import serial.tools.list_ports
from email.mime.text import MIMEText
import os
from datetime import datetime, timedelta
import requests
import threading
import csv
import threading
import queue
from time import sleep

ser = None
data_queue = queue.Queue()
DEBUG_PRINT_INPUT = False
webhook_url = "https://discord.com/api/webhooks/1162935020697157642/nj-BYDIRYbqAgsXncA2rcl3Rk9Y4hAVIhPXjAXNZBoU2zGK8nW_E_tLqLke-CXq5mTV_"
last_email_times = {i: datetime.min for i in range(16)}
sender_email = "bmslab1183@gmail.com"
password = "mwli pqme vufj wgln"

def read_serial():
    global ser  # Make sure to declare 'ser' as global
    while True:
        if ser is not None and ser.is_open:
            try:
                ser_data = ser.readline().decode('utf-8').strip()
                if DEBUG_PRINT_INPUT:
                    print("Raw Data:", ser_data)  # Debugging line to check raw serial data

                # Handling malformed JSON
                if ser_data.endswith(',\"\"}'):
                    ser_data = ser_data[:-4] + '}'

                processed_data = json.loads(ser_data)
                data_queue.put(processed_data)
            except json.JSONDecodeError:
                print("Failed to decode JSON. Received:", ser_data)
            except serial.SerialTimeoutException:
                print("Read timeout - No data received.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to read serial data: {str(e)}")
        else:
            print("Serial port not initialized or not open.")
        sleep(0.1)


def update_gui():
    try:
        # Check if there is new data in the queue
        while not data_queue.empty():
            data = data_queue.get_nowait()
            # Record the refresh time when data is received
            last_refreshed_time.set(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            # Update labels for received data
            for key, temp_str in data.items():
                i = int(key)  # Convert key to zero-based index
                if probes_var[i].get():  # Check if the probe is enabled
                    temp = float(temp_str)  # Convert string to float
                    labels[i].config(text=f"G{i+1:03}: {temp}°C")
                    
                    # Check the condition for sending an email
                    if temp > max_temp_var.get() and send_emails.get():
                        now = datetime.now()  # Get the current time
                        delta = now - last_email_times[i]  # Calculate time delta since last email
                        
                        # Check if it's been more than 5 minutes
                        if delta.total_seconds() >= 300:  # 5 minutes = 300 seconds
                            last_email_times[i] = now  # Update the last email time for this probe
                            
                            # Start a new thread to send the email
                            send_email_thread = threading.Thread(
                                target=send_email,
                                args=(
                                    "Temperature Alert",
                                    f"G{i+1:03} has reached {temp}°C",
                                ),
                            )
                            send_email_thread.start()

            # Write to CSV (if this part of the requirement still exists)
            write_to_csv(data, last_refreshed_time.get())

    except ValueError:
        messagebox.showerror("Error", "Received an invalid temperature reading.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to update GUI: {str(e)}")

    # Schedule the next GUI update
    root.after(100, update_gui)

def select_csv_file():
    global CSV_FILE_NAME
    filename = filedialog.asksaveasfilename(
        title="Select file",
        filetypes=(("CSV files", "*.csv"), ("all files", "*.*")),
        defaultextension=".csv"
    )
    if filename:  # If a file was selected
        CSV_FILE_NAME = filename
        csv_file_label_var.set(CSV_FILE_NAME)  # Update the label or entry with the file path


def write_to_csv(data):
    global CSV_FILE_NAME  # Ensure you are using the global variable
    if not CSV_FILE_NAME:  # Check if the CSV_FILE_NAME is set
        print("CSV file name is not set.")
        return

    # Check if the file exists to determine if we need to write headers
    file_exists = os.path.isfile(CSV_FILE_NAME)

    # Open the file in append mode ('a')
    with open(CSV_FILE_NAME, mode='a', newline='') as file:
        writer = csv.writer(file)

        # Write the header if the file is new
        if not file_exists:
            header = ['Timestamp'] + [f"Probe{i+1:02}" for i in range(16)]
            writer.writerow(header)

        # Create a row with the timestamp and probe data
        row = [datetime.now().strftime("%Y-%m-%d %H:%M:%S")] + [data.get(str(i), 'N/A') for i in range(16)]
        writer.writerow(row)

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
        recipient_emails = list(email_listbox.get(0, tk.END))
    
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = ", ".join(recipient_emails)
    
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, recipient_emails, msg.as_string())
        server.quit()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to send email: {str(e)}")

def connect_serial():
    global ser
    try:
        ser = serial.Serial(port_combobox.get(), 9600, timeout=1)
        connect_button.config(text="Disconnect")
        port_combobox.config(state=tk.DISABLED)
        
        # Start the serial reading in a separate thread only after successful connection
        serial_thread = threading.Thread(target=read_serial, daemon=True)
        serial_thread.start()
        # Debug print plus 1 hour
        print("Started scheduled reconnect, next reconnect at ", (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        messagebox.showerror("Error", f"Failed to connect to serial port: {str(e)}")

def disconnect_serial():
    global ser
    try:
        if ser.is_open:
            ser.close()
        connect_button.config(text="Connect")
        port_combobox.config(state=tk.NORMAL)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to disconnect serial port: {str(e)}")


def toggle_serial_connection():
    global ser, serial_thread  # Add 'serial_thread' as a global variable
    if connect_button["text"] == "Connect":
        CSV_FILE_NAME = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        connect_serial()
    else:
        disconnect_serial()
def scheduled_reconnect():
    # Only proceed if the serial connection is open
    if ser.is_open:
        disconnect_serial()
        # Wait a short period of time before reconnecting, to ensure the buffer is cleared and the port is closed properly
        threading.Timer(5, connect_serial).start()


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
    dir_path = os.path.dirname(os.path.realpath(__file__))
    try:
        if os.path.exists(dir_path+"/emails.json"):
            with open(dir_path+"/emails.json", "r") as file:
                emails = json.load(file)
                for email in emails:
                    email_listbox.insert(tk.END, email)
    except Exception as e:
        print("Error", f"Failed to open emails: {str(e)}")
    
def send_test_email():
    try:
        send_email("Test Email", "This is a test email from your Temperature Monitoring System.")
        messagebox.showinfo("Success", "Test email sent successfully!")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to send test email: {str(e)}")

def save_max_temp():
    try:
        max_temp = float(max_temp_var.get())
        if max_temp < 0 or max_temp > 250:
            messagebox.showerror("Error", "Max temp must be between 0 and 50")
        else:
            max_temp = round(max_temp, 1)
            max_temp_var.set(max_temp)
            max_temp_entry.delete(0, tk.END)
            max_temp_entry.insert(0, max_temp)
            max_temp = ttk.Label(control_frame, text=f"Max Temp: {max_temp}°C")
            max_temp.grid(row=0, column=3, padx=5, pady=5, sticky=tk.EW)
    except ValueError:
        messagebox.showerror("Error", "Max temp must be a number")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save max temp: {str(e)}")


# Start Sending Emails Button
def toggle_send_emails():
    send_emails.set(not send_emails.get())
    email_button.config(text="Stop Sending Emails" if send_emails.get() else "Start Sending Emails")




# GUI
root = tk.Tk()
root.title("Temperature Monitoring")

# Schedule the first GUI update
root.after(100, update_gui)

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
# Email Frame
email_frame = ttk.Frame(root)
email_frame.grid(row=1, column=0, padx=20, pady=5, sticky=tk.EW)
email_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand
# CSV File Frame
csv_frame = ttk.Frame(root)
csv_frame.grid(row=2, column=0, padx=20, pady=5, sticky=tk.EW)
csv_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand
# Temperature Display and Control Frame
temp_frame = ttk.Frame(root)
temp_frame.grid(row=3, column=0, padx=20, pady=5, sticky=tk.W)
temp_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand
# Max Temp Controls Frame
control_frame = ttk.Frame(root)
control_frame.grid(row=4, column=0, padx=20, pady=5, sticky=tk.EW)
control_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand
# Refresh Rate Control Frame
refresh_frame = ttk.Frame(root)
refresh_frame.grid(row=5, column=0, padx=20, pady=5, sticky=tk.EW)
refresh_frame.columnconfigure(3, weight=1)  # Allow column 1 to expand
# Send Configuration Button
send_config_frame = ttk.Frame(root)
send_config_frame.grid(row=6, column=0, padx=20, pady=5, sticky=tk.EW)
send_config_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand
# Last Refreshed Label
last_refreshed_frame = ttk.Frame(root)
last_refreshed_frame.grid(row=7, column=0, padx=20, pady=5, sticky=tk.EW)
last_refreshed_frame.columnconfigure(1, weight=1)  # Allow column 1 to expand

# Serial Frame
# Serial Port Label and Combobox
ttk.Label(serial_frame, text="Select Serial Port:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
port_combobox = ttk.Combobox(serial_frame, values=[comport.device for comport in serial.tools.list_ports.comports() if "ttyS0" not in comport.device])
port_combobox.grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
if port_combobox['values']:
    port_combobox.current(0)
else:
    messagebox.showerror("Error", "No serial ports found")
# Connect Button
connect_button = ttk.Button(serial_frame, text="Connect", command=toggle_serial_connection)
connect_button.grid(row=0, column=2, padx=5, pady=5)

# Email Frame
# Add Email Controls
ttk.Label(email_frame, text="Add Email:").grid(row=0, column=0)
email_entry = ttk.Entry(email_frame).grid(row=0, column=1, padx=20, pady=5, columnspan=1)
email_add_button = ttk.Button(email_frame, text="Add", command=add_email).grid(row=0, column=2, padx=5, pady=5)
# Test Email Button
email_test_button = ttk.Button(email_frame, text="Send Test Email", command=send_test_email).grid(row=1, column=0)
email_button = ttk.Button(email_frame, text="Start Sending Emails", command=toggle_send_emails).grid(row=1, column=1)
# Email Listbox
email_listbox = tk.Listbox(email_frame, selectmode=tk.SINGLE, height=5)
email_listbox.grid(row=2, column=0, padx=20, pady=5, sticky=tk.EW, columnspan=3)
email_listbox.bind("<Double-Button-1>", remove_email)
# Load email recipients from file
load_emails()

# CSV File Frame
# CSV File Controls
csv_file_label_var = tk.StringVar(value="No file selected")
csv_file_label = ttk.Entry(csv_frame, textvariable=csv_file_label_var, state='readonly')  # Use 'normal' state to allow editing
csv_file_label.grid(row=8, column=0, padx=20, pady=5, sticky=tk.EW, columnspan=4)
select_csv_button = ttk.Button(csv_frame, text="Select CSV File", command=select_csv_file)
select_csv_button.grid(row=9, column=0, padx=20, pady=5, columnspan=4)

# Temp Control Frame
# Temperature Display and Control Frame
labels = [ttk.Label(temp_frame, text=f"G{i+1:03}: --°C") for i in range(16)]
for i, (label, var) in enumerate(zip(labels, probes_var)):
    label.grid(row=i, column=0, padx=20, pady=2, sticky=tk.W)
    ttk.Checkbutton(temp_frame, text=f"Disable G{i+1:03}", variable=var).grid(row=i, column=1, padx=20, pady=2, sticky=tk.W)


# Refresh Rate Control Frame
ttk.Label(refresh_frame, text="Refresh Rate (s):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
refresh_rate_entry = ttk.Entry(refresh_frame, textvariable=refresh_rate_var)
refresh_rate_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

# Max Temp Controls Frame
# Max Temp Entry
ttk.Label(control_frame, text="Max Temp (°C):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.E)
max_temp_entry = ttk.Entry(control_frame, textvariable=max_temp_var)
max_temp_entry.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
# Save Max Temp Button
max_temp_button = ttk.Button(control_frame, text="Save Temp", command=save_max_temp)
max_temp_button.grid(row=0, column=2, padx=5, pady=5, sticky=tk.EW)
# Show max temp
max_temp = ttk.Label(control_frame, text=f"Max Temp: {max_temp_var.get()}°C")
max_temp.grid(row=0, column=3, padx=5, pady=5, sticky=tk.EW)

# Label to display the last refreshed timestamp
last_refreshed_label = ttk.Label(last_refreshed_frame, textvariable=last_refreshed_time)
last_refreshed_label.grid(row=1, column=0, padx=20, pady=5, sticky=tk.W)

# Send Configuration Button
send_config_button = ttk.Button(send_config_frame, text="Send Config to Arduino", command=send_serial_config)
send_config_button.grid(row=1, column=0, padx=20, pady=5)

root.columnconfigure(0, weight=1)  # Allow column 0 to expand
root.mainloop()

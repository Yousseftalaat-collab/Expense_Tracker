import tkinter as tk
from tkinter import ttk
import requests
import json
import os

def fetch_exchange_rates():
    url = "https://api.exchangerate-api.com/v4/latest/USD" 
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            return data.get("rates", {})
        else:
            print("Error fetching rates:", response.status_code)
            return {}
    except Exception as e:
        print("API Error:", e)
        return {}


RATES_TO_USD = fetch_exchange_rates()

def convert_to_usd(amount_str, currency_code):
    try:
        amt = float(amount_str)
    except ValueError:
        return 0.0

    if currency_code == "USD":
        return amt
    rate = RATES_TO_USD.get(currency_code, 0)
    return amt / rate if rate else 0.0

# save & load by json 
DATA_FILE = "expenses.json"

def save_expenses():
    expenses = []
    for iid in expense_table.get_children():
        values = expense_table.item(iid, "values")
        if "TOTAL" in values:  
            continue
        expenses.append({
            "amount": values[0],
            "currency": values[1],
            "category": values[2],
            "payment": values[3]
        })
    with open(DATA_FILE, "w") as f:
        json.dump(expenses, f)

def load_expenses():
    if not os.path.exists(DATA_FILE):
        return
    with open(DATA_FILE, "r") as f:
        expenses = json.load(f)
    for expense in expenses:
        expense_table.insert("", "end", values=(expense["amount"], expense["currency"],
                                                expense["category"], expense["payment"]))
        

#create main window 
window = tk.Tk()
window.title("Expense Tracker")
window.geometry("700x600")
window.resizable(True,True)

# input frame
input_frame = tk.Frame(window)
input_frame.pack(pady=10)

# Amount label
amount_label = tk.Label(input_frame, text= "Amount", font=("Arial",14))
amount_label.grid(row=0, column=0, padx=10, pady=5, sticky="w" )
amount_entry = tk.Entry(input_frame, width=20)
amount_entry.grid(row=0, column=1, padx=10, pady=5)

# currency Dropdown
currency_label = tk.Label(input_frame, text= "Currency", font=("Arial",14))
currency_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
currencies = ["", "USD", "GBP","EURO", "EGP" ]
Currency_combobox = ttk.Combobox(input_frame, values=currencies, state="readonly")
Currency_combobox.grid(row=1, column=1, padx=10, pady=5)
Currency_combobox.current(0)

#category Dropdown
Category_label = tk.Label(input_frame, text="Category", font=("Arial",14))
Category_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
categories =["","Life expense", "Electricity", "Gas", "Rental", "Grocery", "Saving", "Education", "Charity"]
categories_combobox = ttk.Combobox(input_frame, values=categories, state="readonly")
categories_combobox.grid(row=2, column=1, padx=10, pady=5)
categories_combobox.current(0)

# payment method Dropdown 
payment_label = tk.Label(input_frame , text="Payment Method", font= ("Arial",14))
payment_label.grid(row=3, column=0, padx=10, pady=5, sticky="w")
payments = ["","Cash", "Credit Card", "Paypal"]
payments_combobox = ttk.Combobox(input_frame, values=payments, state= "readonly")
payments_combobox.grid(row=3, column=1, padx=10, pady=5)
payments_combobox.current(0)

# Date
date_label = tk.Label(input_frame, text= "Date (YYYY-MM-DD)", font=("Arial",14))
date_label.grid(row=4, column=0,padx=10, pady=5, sticky="w")
date_entry = tk.Entry(input_frame, width=20)
date_entry.grid(row=4, column=1, padx=10, pady=5)

# Date placeholder
def set_date_placeholder():
    if date_entry.get() == "":
        date_entry.insert(0, "YYYY-MM-DD")
        date_entry.config(fg="gray")

        
def clear_date_placeholder(event):
    if date_entry.get() == "YYYY-MM-DD":
        date_entry.delete(0, tk.END)
        date_entry.config(fg="black")

def restore_date_placeholder(event):
    if date_entry.get() == "":
        date_entry.insert(0, "YYYY-MM-DD")
        date_entry.config(fg="gray")


set_date_placeholder()
date_entry.bind("<FocusIn>", clear_date_placeholder)
date_entry.bind("<FocusOut>", restore_date_placeholder)


#button frame 
button_frame = tk.Frame(window)
button_frame.pack(pady=10) 

#add button 
add_button = tk.Button(button_frame, text="Add Expense", font=("Arial", 12, "bold"), bg="#fcfcfc", fg="black")
add_button.grid(row=0, column=0, padx=10)

#delete button 
delete_button = tk.Button(button_frame, text="Delete Expense", font=("Arial", 12, "bold"), bg="#fcfcfc", fg="black")
delete_button.grid(row=0, column=1, padx=10)

#table  
table_frame = tk.Frame(window)
table_frame.pack(pady=20)

columns = ("Amount", "Currency", "Category", "Payment Method")
expense_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=8)
for col in columns:
    expense_table.heading(col, text=col)
    expense_table.column(col, width=150)
expense_table.pack()

style = ttk.Style()
style.map("Treeview", background=[("selected","#347083")])

# total row 
expense_table.tag_configure("total", background="yellow", font=("Arial", 12, "bold"))

#remove total
def remove_total_row():
    for iid in expense_table.get_children():
        if "total" in expense_table.item(iid, "tags"):
            expense_table.delete(iid)

# update total
def update_total():
    remove_total_row()
    total_usd = 0.0
    for iid in expense_table.get_children():

        if "total" in expense_table.item(iid, "tags"):
            continue
        vals = expense_table.item(iid, "values")
        if not vals:
            continue
        amount_str = vals[0]
        currency_code = vals[1]
        total_usd += convert_to_usd(amount_str, currency_code)

    expense_table.insert("", "end",
                         values=("TOTAL", f"{total_usd:.2f}", "USD", ""),
                         tags=("total",))


# Add function
def add_expense():
    amount = amount_entry.get()
    currency = Currency_combobox.get()
    category = categories_combobox.get()
    payment = payments_combobox.get()
    date = date_entry.get()


    if amount == "" or currency == "" or category == "" or payment == "" or date in ("", "YYYY-MM-DD"):
        print("Please fill all fields!")
        return


    try:
        float(amount)
    except ValueError:
        print("Amount must be a number!")
        return


    remove_total_row()
    expense_table.insert("", "end", values=(amount, currency, category, payment))


    amount_entry.delete(0, tk.END)
    Currency_combobox.current(0)
    categories_combobox.current(0)
    payments_combobox.current(0)
    date_entry.delete(0, tk.END)
    set_date_placeholder()

    update_total()
    save_expenses()
    
# delete funcation
def delete_expense():
    selected = expense_table.selection()
    if not selected:
        print("No expense selected!")
        return

    for iid in selected:

        if "total" in expense_table.item(iid, "tags"):
            continue
        expense_table.delete(iid)

    update_total()
    save_expenses()

add_button.config(command=add_expense)
delete_button.config(command=delete_expense)

load_expenses()
update_total()

window.mainloop()
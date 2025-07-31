import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import os
import uuid
from datetime import date

# ============================================================
# Configuration
# ============================================================
DATA_FILE = "expenses.json"          # persisted data
API_URL   = "https://api.exchangerate-api.com/v4/latest/USD"

# currencies offered in UI (first item blank = no selection)
UI_CURRENCIES = ["", "USD", "GBP", "EUR", "EGP", "EURO"]  # EURO auto-mapped -> EUR
UI_CATEGORIES = [
    "", "Life expense", "Electricity", "Gas", "Rental",
    "Grocery", "Saving", "Education", "Charity"
]
UI_PAYMENTS   = ["", "Cash", "Credit Card", "Paypal"]


# ============================================================
# Helpers
# ============================================================
def normalize_currency(code: str) -> str:
    """Map UI value to API/standard 3-letter code."""
    code = (code or "").strip().upper()
    if code == "EURO":
        return "EUR"
    return code


def safe_float(s, default=0.0):
    try:
        return float(s)
    except Exception:
        return default


# ============================================================
# Exchange Rates Manager
# ============================================================
class RateManager:
    def __init__(self, url=API_URL):
        self.url = url
        self.rates = {"USD": 1.0}  # fallback minimal
        # some fallback guesses in case offline
        self.fallback = {"USD": 1.0, "GBP": 1.30, "EUR": 1.10, "EGP": 0.020}

    def fetch(self):
        try:
            resp = requests.get(self.url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                rates = data.get("rates", {})
                if isinstance(rates, dict) and rates:
                    self.rates = rates
                    return True
            # fallthrough -> use fallback
        except Exception as e:
            print("Rate fetch error:", e)
        # fallback
        self.rates = self.fallback.copy()
        return False

    def to_usd(self, amount, currency):
        """Convert an amount *in currency* to USD."""
        amount = safe_float(amount, 0.0)
        c = normalize_currency(currency)
        if c == "USD":
            return amount
        rate = self.rates.get(c)
        if not rate:
            # unknown currency -> try fallback -> still maybe 0
            rate = self.fallback.get(c, 0)
        if not rate:
            return 0.0
        # API: 1 USD = rate (units of currency)
        # amount is in currency; USD = amount / rate
        return amount / rate


# ============================================================
# ExpenseTrackerApp
# ============================================================
class ExpenseTrackerApp:
    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.root.title("Expense Tracker")
        self.root.geometry("780x640")

        # rate manager
        self.rate_mgr = RateManager()
        self.rate_online = self.rate_mgr.fetch()  # fetch once at startup

        # editing state
        self.editing_expense_id = None  # None means we're adding new

        # build UI
        self._build_inputs()
        self._build_buttons()
        self._build_table()
        self._build_statusbar()

        # load persisted data
        self._load_expenses_from_file()
        self._update_total_row()

    # ---------------- UI builders ----------------
    def _build_inputs(self):
        f = ttk.Frame(self.root, padding=(10, 10))
        f.pack(pady=5, fill="x")
        self.input_frame = f

        # Amount
        ttk.Label(f, text="Amount", font=("Arial", 12)).grid(row=0, column=0, sticky="w", padx=5, pady=3)
        self.amount_var = tk.StringVar()
        ttk.Entry(f, textvariable=self.amount_var, width=20).grid(row=0, column=1, padx=5, pady=3)

        # Currency
        ttk.Label(f, text="Currency", font=("Arial", 12)).grid(row=1, column=0, sticky="w", padx=5, pady=3)
        self.currency_var = tk.StringVar()
        ttk.Combobox(f, textvariable=self.currency_var, values=UI_CURRENCIES, state="readonly", width=18)\
            .grid(row=1, column=1, padx=5, pady=3)
        self.currency_var.set("")

        # Category
        ttk.Label(f, text="Category", font=("Arial", 12)).grid(row=2, column=0, sticky="w", padx=5, pady=3)
        self.category_var = tk.StringVar()
        ttk.Combobox(f, textvariable=self.category_var, values=UI_CATEGORIES, state="readonly", width=18)\
            .grid(row=2, column=1, padx=5, pady=3)
        self.category_var.set("")

        # Payment Method
        ttk.Label(f, text="Payment Method", font=("Arial", 12)).grid(row=3, column=0, sticky="w", padx=5, pady=3)
        self.payment_var = tk.StringVar()
        ttk.Combobox(f, textvariable=self.payment_var, values=UI_PAYMENTS, state="readonly", width=18)\
            .grid(row=3, column=1, padx=5, pady=3)
        self.payment_var.set("")

        # Date
        ttk.Label(f, text="Date (YYYY-MM-DD)", font=("Arial", 12)).grid(row=4, column=0, sticky="w", padx=5, pady=3)
        self.date_entry = ttk.Entry(f, width=20)
        self.date_entry.grid(row=4, column=1, padx=5, pady=3)
        self._set_date_placeholder()

        # Today shortcut
        ttk.Button(f, text="Today", command=self._fill_today).grid(row=4, column=2, padx=5, pady=3)

    def _build_buttons(self):
        bf = ttk.Frame(self.root, padding=(10, 5))
        bf.pack(pady=5)
        self.button_frame = bf

        self.add_btn = tk.Button(bf, text="Add", width=10, bg="#4CAF50", fg="white", command=self._on_add_update)
        self.add_btn.grid(row=0, column=0, padx=5)

        self.delete_btn = tk.Button(bf, text="Delete", width=10, bg="#F44336", fg="white", command=self._on_delete)
        self.delete_btn.grid(row=0, column=1, padx=5)

        self.edit_btn = tk.Button(bf, text="Edit Selected", width=12, bg="#2196F3", fg="white", command=self._on_edit_selected)
        self.edit_btn.grid(row=0, column=2, padx=5)

        self.refresh_btn = tk.Button(bf, text="Refresh Rates", width=12, bg="#9C27B0", fg="white", command=self._on_refresh_rates)
        self.refresh_btn.grid(row=0, column=3, padx=5)

        self.clear_btn = tk.Button(bf, text="Clear All", width=10, bg="#FF9800", fg="white", command=self._on_clear_all)
        self.clear_btn.grid(row=0, column=4, padx=5)

    def _build_table(self):
        tf = ttk.Frame(self.root, padding=(10, 5))
        tf.pack(pady=10, fill="both", expand=True)
        self.table_frame = tf

        cols = ("Amount", "Currency", "Category", "Payment")
        tv = ttk.Treeview(tf, columns=cols, show="headings", height=10)
        for c in cols:
            tv.heading(c, text=c)
            tv.column(c, width=150, anchor="center")
        tv.pack(fill="both", expand=True)
        self.expense_table = tv

        # vertical scrollbar
        vsb = ttk.Scrollbar(tf, orient="vertical", command=tv.yview)
        tv.configure(yscroll=vsb.set)
        vsb.pack(side="right", fill="y")

        # tag styling
        tv.tag_configure("total", background="yellow", font=("Arial", 12, "bold"))

        # double-click row triggers edit
        tv.bind("<Double-1>", self._on_double_click_row)

    def _build_statusbar(self):
        sb = tk.Label(self.root, text="", anchor="w", relief="sunken")
        sb.pack(fill="x", side="bottom")
        self.status_bar = sb
        self._set_status("Ready." if self.rate_online else "Using fallback currency rates (offline).")

    # ---------------- Placeholder & Today ----------------
    def _set_date_placeholder(self):
        if not self.date_entry.get():
            self.date_entry.insert(0, "YYYY-MM-DD")
            self.date_entry.config(foreground="gray")
        self.date_entry.bind("<FocusIn>", self._clear_date_placeholder)
        self.date_entry.bind("<FocusOut>", self._restore_date_placeholder)

    def _clear_date_placeholder(self, _evt):
        if self.date_entry.get() == "YYYY-MM-DD":
            self.date_entry.delete(0, tk.END)
            self.date_entry.config(foreground="black")

    def _restore_date_placeholder(self, _evt):
        if not self.date_entry.get():
            self.date_entry.insert(0, "YYYY-MM-DD")
            self.date_entry.config(foreground="gray")

    def _fill_today(self):
        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, date.today().isoformat())
        self.date_entry.config(foreground="black")

    # ---------------- Status helper ----------------
    def _set_status(self, msg):
        self.status_bar.config(text=msg)

    # ============================================================
    # Data storage: we keep a dict expense_id -> record in memory
    # record = {id, amount, currency, category, payment, date}
    # Treeview item iid maps to expense id via self._tree_id_to_expense_id
    # ============================================================
    def _init_storage(self):
        self.expenses = {}  # expense_id -> record
        self._tree_id_to_expense_id = {}  # tree iid -> expense_id

    # load from file called in __init__
    def _load_expenses_from_file(self):
        self._init_storage()
        if not os.path.exists(DATA_FILE):
            self._set_status("No saved data found.")
            return
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._set_status(f"Error loading file: {e}")
            return
        count = 0
        for rec in data:
            # backwards compatibility with old structure (no id)
            exp_id = rec.get("id") or str(uuid.uuid4())
            amount = rec.get("amount", "")
            currency = normalize_currency(rec.get("currency", ""))
            category = rec.get("category", "")
            payment = rec.get("payment", "")
            date_str = rec.get("date", "")
            iid = self.expense_table.insert("", "end",
                                            values=(amount, currency, category, payment))
            self._tree_id_to_expense_id[iid] = exp_id
            self.expenses[exp_id] = {
                "id": exp_id,
                "amount": amount,
                "currency": currency,
                "category": category,
                "payment": payment,
                "date": date_str,
            }
            count += 1
        self._set_status(f"Loaded {count} expenses from file.")

    def _save_expenses_to_file(self):
        data = list(self.expenses.values())
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            self._set_status(f"Saved {len(data)} expenses.")
        except Exception as e:
            self._set_status(f"Error saving: {e}")

    # ============================================================
    # Total row handling
    # ============================================================
    def _remove_total_row(self):
        for iid in self.expense_table.get_children():
            if "total" in self.expense_table.item(iid, "tags"):
                self.expense_table.delete(iid)

    def _update_total_row(self):
        self._remove_total_row()
        total_usd = 0.0
        for exp_id, rec in self.expenses.items():
            total_usd += self.rate_mgr.to_usd(rec["amount"], rec["currency"])
        self.expense_table.insert(
            "", "end",
            values=("TOTAL", f"{total_usd:.2f}", "USD", ""),
            tags=("total",)
        )

    # ============================================================
    # Button Handlers
    # ============================================================
    def _on_add_update(self):
        """Add *or* update depending on editing state."""
        amount = self.amount_var.get()
        currency = normalize_currency(self.currency_var.get())
        category = self.category_var.get()
        payment = self.payment_var.get()
        date_str = self.date_entry.get()

        # validation
        if (not amount or not currency or not category or not payment or
                date_str in ("", "YYYY-MM-DD")):
            self._set_status("Fill all fields before adding.")
            return

        if safe_float(amount, None) is None:
            self._set_status("Amount must be numeric.")
            return

        # editing?
        if self.editing_expense_id:
            self._apply_edit(self.editing_expense_id, amount, currency, category, payment, date_str)
        else:
            self._add_new(amount, currency, category, payment, date_str)

        # reset form & button text
        self._reset_form()

    def _add_new(self, amount, currency, category, payment, date_str):
        self._remove_total_row()
        iid = self.expense_table.insert("", "end",
                                        values=(amount, currency, category, payment))
        exp_id = str(uuid.uuid4())
        self._tree_id_to_expense_id[iid] = exp_id
        self.expenses[exp_id] = {
            "id": exp_id,
            "amount": amount,
            "currency": currency,
            "category": category,
            "payment": payment,
            "date": date_str,
        }
        self._save_expenses_to_file()
        self._update_total_row()
        self._set_status("Expense added.")

    def _apply_edit(self, exp_id, amount, currency, category, payment, date_str):
        # update memory
        rec = self.expenses.get(exp_id)
        if not rec:
            self._set_status("Could not find expense to update.")
            return
        rec.update({
            "amount": amount,
            "currency": currency,
            "category": category,
            "payment": payment,
            "date": date_str,
        })
        # update table row (find iid)
        for iid, eid in self._tree_id_to_expense_id.items():
            if eid == exp_id:
                # skip total row
                if "total" in self.expense_table.item(iid, "tags"):
                    continue
                self.expense_table.item(iid, values=(amount, currency, category, payment))
                break
        self._save_expenses_to_file()
        self._update_total_row()
        self._set_status("Expense updated.")
        self.editing_expense_id = None
        self.add_btn.config(text="Add")

    def _on_delete(self):
        selection = self.expense_table.selection()
        if not selection:
            self._set_status("Select a row to delete.")
            return
        deleted = 0
        for iid in selection:
            if "total" in self.expense_table.item(iid, "tags"):
                continue
            exp_id = self._tree_id_to_expense_id.pop(iid, None)
            if exp_id and exp_id in self.expenses:
                del self.expenses[exp_id]
            self.expense_table.delete(iid)
            deleted += 1
        self._save_expenses_to_file()
        self._update_total_row()
        self._set_status(f"Deleted {deleted} expense(s).")

    def _on_edit_selected(self):
        """Load first selected row into form for editing."""
        selection = self.expense_table.selection()
        if not selection:
            self._set_status("Select a row to edit.")
            return
        iid = selection[0]
        if "total" in self.expense_table.item(iid, "tags"):
            self._set_status("Cannot edit total row.")
            return
        exp_id = self._tree_id_to_expense_id.get(iid)
        if not exp_id:
            self._set_status("Internal ID missing; cannot edit.")
            return
        rec = self.expenses.get(exp_id)
        if not rec:
            self._set_status("Expense record not found.")
            return

        # load into form
        self.amount_var.set(rec["amount"])
        self.currency_var.set(rec["currency"])
        self.category_var.set(rec["category"])
        self.payment_var.set(rec["payment"])

        self.date_entry.delete(0, tk.END)
        self.date_entry.insert(0, rec.get("date", ""))
        self.date_entry.config(foreground="black")

        self.editing_expense_id = exp_id
        self.add_btn.config(text="Update")
        self._set_status("Editing mode: make changes and click Update.")

    def _on_double_click_row(self, _evt):
        self._on_edit_selected()

    def _on_refresh_rates(self):
        online = self.rate_mgr.fetch()
        self.rate_online = online
        self._update_total_row()
        self._set_status("Rates refreshed." if online else "Rates refresh failed; using fallback.")

    def _on_clear_all(self):
        if not messagebox.askyesno("Confirm", "Delete ALL expenses?"):
            return
        # clear table
        for iid in self.expense_table.get_children():
            self.expense_table.delete(iid)
        # clear memory
        self._init_storage()
        self._save_expenses_to_file()
        self._update_total_row()
        self._set_status("All expenses cleared.")

    # ---------------- form reset ----------------
    def _reset_form(self):
        self.amount_var.set("")
        self.currency_var.set("")
        self.category_var.set("")
        self.payment_var.set("")
        self.date_entry.delete(0, tk.END)
        self._restore_date_placeholder(None)
        self.editing_expense_id = None
        self.add_btn.config(text="Add")

    # ---------------- run ----------------
    def run(self):
        self.root.mainloop()


# ============================================================
# Run the app
# ============================================================
if __name__ == "__main__":
    app = ExpenseTrackerApp()
    app.run()

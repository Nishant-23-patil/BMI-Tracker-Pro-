#!/usr/bin/env python3
"""
BMI Tracker Pro — v2 · Authenticated
═══════════════════════════════════════════════════════════════════════════════
Role-based access control:
  • Admin  — full access: view/add/delete any user, see all data
  • User   — restricted: can only view their own BMI history & records

Default admin credentials (created automatically on first run):
    Username : admin
    Password : admin123

Usage:
    python bmi_gui.py

Optional dependency (for charts):
    pip install matplotlib
═══════════════════════════════════════════════════════════════════════════════
"""
import os
import math
import sqlite3
import hashlib
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

# ── Optional matplotlib ───────────────────────────────────────────────────────
try:
    import matplotlib
    import matplotlib.dates as mdates
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


# ══════════════════════════════════════════════════════════════════════════════
#  THEME
# ══════════════════════════════════════════════════════════════════════════════
BG0  = "#0d1117"   # root background
BG1  = "#161b22"   # sidebar / panel
BG2  = "#1c2128"   # card / elevated surface
BG3  = "#21262d"   # input / hover
ACC  = "#4361ee"   # primary accent – blue
TEAL = "#06b6d4"   # teal accent
PURP = "#7c3aed"   # purple accent (admin)
TXP  = "#e6edf3"   # primary text
TXS  = "#8b949e"   # secondary text
TXM  = "#484f58"   # muted text
BDR  = "#30363d"   # border
GRN  = "#4ade80"   # success / normal weight
YEL  = "#fbbf24"   # warning / overweight
ORG  = "#fb923c"   # obese I
RED  = "#f87171"   # danger / obese II+
CYN  = "#38bdf8"   # info / underweight
FNT  = "Segoe UI"

CATS = [
    (0,    16,   "Severe Underweight", "#ef4444"),
    (16,   18.5, "Underweight",        CYN      ),
    (18.5, 25,   "Normal Weight",      GRN      ),
    (25,   30,   "Overweight",         YEL      ),
    (30,   35,   "Obese Class I",      ORG      ),
    (35,   40,   "Obese Class II",     RED      ),
    (40,   999,  "Obese Class III",    "#dc2626" ),
]

ADVICE = {
    "Severe Underweight": "Very low body weight. Please consult a doctor immediately.",
    "Underweight":        "Below the healthy range. A nutritionist can help you gain healthily.",
    "Normal Weight":      "Excellent! You have a healthy BMI. Keep up your great lifestyle!",
    "Overweight":         "Slightly above the healthy range. Balanced diet & exercise can help.",
    "Obese Class I":      "Class I obesity. Lifestyle changes are strongly recommended.",
    "Obese Class II":     "Class II obesity. Please consult a healthcare professional.",
    "Obese Class III":    "Severe obesity. Please seek immediate medical attention.",
}

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bmi_tracker.db")
G_MIN, G_MAX = 10.0, 45.0


# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _hash(pw: str) -> str:
    """SHA-256 hash a password string."""
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def bmi_to_angle(bmi: float) -> float:
    t = (max(G_MIN, min(G_MAX, float(bmi))) - G_MIN) / (G_MAX - G_MIN)
    return 180.0 - t * 180.0


def get_cat(bmi: float):
    for lo, hi, cat, color in CATS:
        if lo <= bmi < hi:
            return cat, color
    return CATS[-1][2], CATS[-1][3]


def lighten(hex_col: str, amount: int = 22) -> str:
    r = min(255, int(hex_col[1:3], 16) + amount)
    g = min(255, int(hex_col[3:5], 16) + amount)
    b = min(255, int(hex_col[5:7], 16) + amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def flat_btn(parent, text, command, bg=ACC, fg=TXP, size=10, **kw):
    b = tk.Button(
        parent, text=text, command=command,
        font=(FNT, size, "bold"), bg=bg, fg=fg,
        activebackground=lighten(bg), activeforeground=fg,
        relief="flat", bd=0, cursor="hand2", padx=14, pady=8, **kw
    )
    b.bind("<Enter>", lambda _: b.config(bg=lighten(bg)))
    b.bind("<Leave>", lambda _: b.config(bg=bg))
    return b


def lbl(parent, text, size=10, bold=False, color=TXP, bg=None, **kw):
    return tk.Label(
        parent, text=text,
        font=(FNT, size, "bold" if bold else "normal"),
        fg=color, bg=bg if bg is not None else parent.cget("bg"), **kw
    )


def entry_widget(parent, var=None, width=20, show="", **kw):
    return tk.Entry(
        parent, textvariable=var, font=(FNT, 12), show=show,
        bg=BG3, fg=TXP, insertbackground=TXP,
        relief="flat", bd=0, highlightthickness=2,
        highlightcolor=ACC, highlightbackground=BDR,
        width=width, **kw
    )


def hdiv(parent, pady=0):
    tk.Frame(parent, bg=BDR, height=1).pack(fill="x", pady=pady)


# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE  (with authentication)
# ══════════════════════════════════════════════════════════════════════════════
class Database:
    """
    SQLite persistence with role-based user management.

    users  : id, name, age, gender, password (SHA-256), role ('admin'|'user'), created
    records: id, uid→users(CASCADE), weight, height, bmi, cat, notes, ts
    """

    def __init__(self):
        with self._cx() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    name     TEXT    NOT NULL UNIQUE,
                    age      INTEGER,
                    gender   TEXT,
                    password TEXT    NOT NULL DEFAULT '',
                    role     TEXT    NOT NULL DEFAULT 'user',
                    created  TEXT    DEFAULT (datetime('now','localtime'))
                );
                CREATE TABLE IF NOT EXISTS records (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    uid      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    weight   REAL    NOT NULL,
                    height   REAL    NOT NULL,
                    bmi      REAL    NOT NULL,
                    cat      TEXT    NOT NULL,
                    notes    TEXT    DEFAULT '',
                    ts       TEXT    DEFAULT (datetime('now','localtime'))
                );
            """)
        self._migrate()
        self._seed_admin()

    def _cx(self):
        c = sqlite3.connect(DB_PATH)
        c.execute("PRAGMA foreign_keys = ON")
        return c

    def _migrate(self):
        """Add new columns to legacy databases without losing data."""
        with self._cx() as c:
            for col, defn in [
                ("password", "TEXT NOT NULL DEFAULT ''"),
                ("role",     "TEXT NOT NULL DEFAULT 'user'"),
            ]:
                try:
                    c.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
                except sqlite3.OperationalError:
                    pass  # column already exists

    def _seed_admin(self):
        """Create the default admin account if no admin exists."""
        with self._cx() as c:
            n = c.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
            if n == 0:
                c.execute(
                    "INSERT OR IGNORE INTO users(name, password, role) VALUES(?,?,?)",
                    ("admin", _hash("admin123"), "admin")
                )

    # ── Authentication ─────────────────────────────────────────────────────
    def verify_login(self, name: str, password: str):
        """Return (id, name, age, gender, role) or None."""
        with self._cx() as c:
            return c.execute(
                "SELECT id, name, age, gender, role FROM users "
                "WHERE name=? AND password=?",
                (name, _hash(password))
            ).fetchone()

    def change_password(self, uid: int, new_password: str):
        with self._cx() as c:
            c.execute("UPDATE users SET password=? WHERE id=?",
                      (_hash(new_password), uid))

    # ── User CRUD ──────────────────────────────────────────────────────────
    def get_users(self):
        """Return [(id, name, age, gender, role), ...] — admin only."""
        with self._cx() as c:
            return c.execute(
                "SELECT id, name, age, gender, role FROM users ORDER BY role DESC, name"
            ).fetchall()

    def add_user(self, name, age=None, gender=None, password="", role="user"):
        with self._cx() as c:
            return c.execute(
                "INSERT INTO users(name, age, gender, password, role) VALUES(?,?,?,?,?)",
                (name, age, gender, _hash(password), role)
            ).lastrowid

    def del_user(self, uid: int):
        with self._cx() as c:
            c.execute("DELETE FROM users WHERE id=?", (uid,))

    # ── Record CRUD ────────────────────────────────────────────────────────
    def get_records(self, uid: int):
        with self._cx() as c:
            return c.execute(
                "SELECT id, weight, height, bmi, cat, notes, ts "
                "FROM records WHERE uid=? ORDER BY ts DESC",
                (uid,)
            ).fetchall()

    def add_record(self, uid, weight, height, bmi, cat, notes=""):
        with self._cx() as c:
            return c.execute(
                "INSERT INTO records(uid, weight, height, bmi, cat, notes) VALUES(?,?,?,?,?,?)",
                (uid, weight, height, bmi, cat, notes)
            ).lastrowid

    def del_record(self, rid: int):
        with self._cx() as c:
            c.execute("DELETE FROM records WHERE id=?", (rid,))

    def get_stats(self, uid: int):
        with self._cx() as c:
            r = c.execute(
                "SELECT COUNT(*), MIN(bmi), MAX(bmi), AVG(bmi) "
                "FROM records WHERE uid=?", (uid,)
            ).fetchone()
        return None if not r or r[0] == 0 else \
               {"count": r[0], "bmi_min": r[1], "bmi_max": r[2], "bmi_avg": r[3]}

    def get_trend(self, uid: int):
        with self._cx() as c:
            rows = c.execute(
                "SELECT ts, bmi, weight FROM records WHERE uid=? ORDER BY ts", (uid,)
            ).fetchall()
        if not rows:
            return [], [], []
        ts, bmi, wt = zip(*rows)
        return list(ts), list(bmi), list(wt)


db = Database()


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN FRAME
# ══════════════════════════════════════════════════════════════════════════════
class LoginFrame(tk.Frame):
    """
    Full-window login screen shown at startup.
    Calls on_success(user_row) where user_row = (id, name, age, gender, role).
    """

    def __init__(self, parent, on_success):
        super().__init__(parent, bg=BG0)
        self._on_success = on_success
        self._show_pw    = False
        self.mode        = "signin"  # "signin" or "signup"
        self._build()

    def _build(self):
        # ── Centred card ──────────────────────────────────────────────────
        wrap = tk.Frame(self, bg=BG0)
        wrap.place(relx=0.5, rely=0.5, anchor="center")

        # App title
        tk.Label(wrap, text="BMI Tracker Pro",
                 font=(FNT, 24, "bold"), fg=ACC, bg=BG0).pack()
        tk.Label(wrap, text="Secure Health Management System",
                 font=(FNT, 10), fg=TXS, bg=BG0).pack(pady=(2, 28))

        # Card
        self.card = tk.Frame(wrap, bg=BG1, padx=40, pady=34)
        self.card.pack()

        self.v_title = tk.StringVar(value="Sign In")
        self.title_lbl = tk.Label(self.card, textvariable=self.v_title, font=(FNT, 15, "bold"), fg=TXP, bg=BG1)
        self.title_lbl.pack(anchor="w", pady=(0, 22))

        # Username field
        lbl(self.card, "Username", 9, color=TXS).pack(anchor="w")
        self.v_name = tk.StringVar()
        self._name_entry = entry_widget(self.card, self.v_name, width=28)
        self._name_entry.pack(anchor="w", ipady=8, pady=(4, 16))

        # Password field
        lbl(self.card, "Password", 9, color=TXS).pack(anchor="w")
        pw_row = tk.Frame(self.card, bg=BG1)
        pw_row.pack(anchor="w", pady=(4, 16))
        self.v_pw = tk.StringVar()
        self._pw_entry = entry_widget(pw_row, self.v_pw, width=24, show="•")
        self._pw_entry.pack(side="left")
        # Eye toggle button
        self._eye_btn = tk.Button(
            pw_row, text="○", font=(FNT, 10), bg=BG3, fg=TXS,
            relief="flat", bd=0, cursor="hand2", padx=6,
            command=self._toggle_pw
        )
        self._eye_btn.pack(side="left", padx=(6, 0), ipady=6)

        # ── Age + Gender fields (Sign Up Mode Only) ──────────────────────────
        self.age_gender_frame = tk.Frame(self.card, bg=BG1)
        
        # Age
        af = tk.Frame(self.age_gender_frame, bg=BG1)
        af.pack(side="left", padx=(0, 16))
        lbl(af, "Age", 9, color=TXS).pack(anchor="w")
        self.v_age = tk.StringVar()
        self._age_entry = entry_widget(af, self.v_age, width=6)
        self._age_entry.pack(anchor="w", ipady=8, pady=(4, 0))

        # Gender
        gf = tk.Frame(self.age_gender_frame, bg=BG1)
        gf.pack(side="left")
        lbl(gf, "Gender", 9, color=TXS).pack(anchor="w")
        self.v_gender = tk.StringVar(value="")
        gr = tk.Frame(gf, bg=BG1)
        gr.pack(pady=(6, 0))
        for g in ("Male", "Female", "Other"):
            tk.Radiobutton(gr, text=g, variable=self.v_gender, value=g,
                           font=(FNT, 9), bg=BG1, fg=TXP,
                           selectcolor=BG3, activebackground=BG1
                           ).pack(side="left", padx=(0, 6))

        # Buttons Frame
        self.btn_frame = tk.Frame(self.card, bg=BG1)
        self.btn_frame.pack(fill="x", pady=(10, 0))

        # Action Button
        self.submit_btn = flat_btn(self.btn_frame, "      Sign In  →      ", self._login,
                                   bg=ACC, size=11)
        self.submit_btn.pack(fill="x", pady=(0, 10))

        # Mode Toggle Link
        self.toggle_btn = tk.Button(
            self.btn_frame, text="Don't have an account? Sign Up", font=(FNT, 9, "underline"),
            fg=TEAL, bg=BG1, activebackground=BG1, activeforeground=lighten(TEAL),
            relief="flat", bd=0, cursor="hand2", command=self._toggle_mode
        )
        self.toggle_btn.pack(fill="x", pady=(0, 10))

        # Error label
        self.v_err = tk.StringVar()
        self.err_lbl = tk.Label(self.card, textvariable=self.v_err, font=(FNT, 9),
                                fg=RED, bg=BG1)
        self.err_lbl.pack()

        # Hint (Sign In Mode Only)
        self.hint_frame = tk.Frame(self.card, bg=BG1)
        self.hint_frame.pack(pady=(18, 0))
        lbl(self.hint_frame, "Default admin:", 8, color=TXM).pack(side="left")
        lbl(self.hint_frame, "  admin / admin123", 8, color=TXS).pack(side="left")

        # Key bindings
        self._pw_entry.bind("<Return>", lambda _: self._login())
        self._name_entry.bind("<Return>", lambda _: self._pw_entry.focus())
        self.v_name.trace_add("write", lambda *_: self.v_err.set(""))
        self.v_pw.trace_add("write",   lambda *_: self.v_err.set(""))

        # Auto-focus username field
        self.after(100, self._name_entry.focus)

    def _toggle_pw(self):
        self._show_pw = not self._show_pw
        self._pw_entry.config(show="" if self._show_pw else "•")
        self._eye_btn.config(text="●" if self._show_pw else "○")

    def _toggle_mode(self):
        self.v_err.set("")
        if self.mode == "signin":
            self.mode = "signup"
            self.v_title.set("Create Account")
            self.submit_btn.config(text="  Create Account & Sign In  ")
            self.toggle_btn.config(text="Already have an account? Sign In")
            self.age_gender_frame.pack(before=self.btn_frame, fill="x", pady=(0, 16))
            self.hint_frame.pack_forget()
        else:
            self.mode = "signin"
            self.v_title.set("Sign In")
            self.submit_btn.config(text="      Sign In  →      ")
            self.toggle_btn.config(text="Don't have an account? Sign Up")
            self.age_gender_frame.pack_forget()
            self.hint_frame.pack(pady=(18, 0))

    def _login(self):
        name = self.v_name.get().strip()
        pw   = self.v_pw.get()
        if not name or not pw:
            self.v_err.set("Please enter both username and password.")
            return

        if self.mode == "signin":
            user = db.verify_login(name, pw)
            if user:
                self._on_success(user)   # (id, name, age, gender, role)
            else:
                self.v_err.set("Invalid username or password.")
                self.v_pw.set("")
                self._pw_entry.focus()
        else:
            # Sign Up Mode
            if len(pw) < 4:
                self.v_err.set("Password must be at least 4 characters.")
                return
            
            with db._cx() as c:
                exists = c.execute("SELECT 1 FROM users WHERE name=?", (name,)).fetchone()
            if exists:
                self.v_err.set(f"Username '{name}' is already taken.")
                return

            age = None
            if self.v_age.get().strip():
                try:
                    age = int(self.v_age.get())
                    assert 1 <= age <= 149
                except (ValueError, AssertionError):
                    self.v_err.set("Enter a valid age (1–149).")
                    return
            
            gender = self.v_gender.get() or None
            
            try:
                uid = db.add_user(name, age, gender, pw, role="user")
                user = (uid, name, age, gender, "user")
                self._on_success(user)
            except Exception as e:
                self.v_err.set("Error during registration. Try another name.")


# ══════════════════════════════════════════════════════════════════════════════
#  CHANGE PASSWORD DIALOG
# ══════════════════════════════════════════════════════════════════════════════
class ChangePasswordDialog(tk.Toplevel):
    """Let any user change their own password."""

    def __init__(self, parent, uid: int, username: str):
        super().__init__(parent)
        self.uid      = uid
        self.title("Change Password")
        self.resizable(False, False)
        self.configure(bg=BG1)
        self.transient(parent)
        self.grab_set()
        self._build(username)
        self.geometry(
            f"360x310+{parent.winfo_rootx()+130}+{parent.winfo_rooty()+100}"
        )
        self.wait_visibility()
        self.focus_force()

    def _build(self, username: str):
        f = tk.Frame(self, bg=BG1, padx=26, pady=22)
        f.pack(fill="both", expand=True)

        lbl(f, "Change Password", 14, bold=True).pack(anchor="w", pady=(0, 6))
        lbl(f, f"Account: {username}", 9, color=TXS).pack(anchor="w", pady=(0, 18))

        for attr, text in [
            ("v_cur",  "Current Password"),
            ("v_new",  "New Password"),
            ("v_con",  "Confirm New Password"),
        ]:
            lbl(f, text, 9, color=TXS).pack(anchor="w")
            var = tk.StringVar()
            setattr(self, attr, var)
            entry_widget(f, var, width=28, show="•").pack(
                anchor="w", ipady=7, pady=(4, 14)
            )

        bf = tk.Frame(f, bg=BG1)
        bf.pack(fill="x")
        flat_btn(bf, "Cancel", self.destroy, bg=BG3, fg=TXS).pack(side="left")
        flat_btn(bf, "  Save  ", self._save, bg=GRN, fg="#0d1117").pack(side="right")

    def _save(self):
        cur = self.v_cur.get()
        new = self.v_new.get()
        con = self.v_con.get()

        # Verify current password
        with sqlite3.connect(DB_PATH) as c:
            ok = c.execute(
                "SELECT 1 FROM users WHERE id=? AND password=?",
                (self.uid, _hash(cur))
            ).fetchone()
        if not ok:
            messagebox.showerror("Error", "Current password is incorrect.", parent=self)
            return
        if len(new) < 4:
            messagebox.showerror("Error", "New password must be at least 4 characters.", parent=self)
            return
        if new != con:
            messagebox.showerror("Error", "New passwords do not match.", parent=self)
            return
        db.change_password(self.uid, new)
        messagebox.showinfo("Success", "Password changed successfully.", parent=self)
        self.destroy()


# ══════════════════════════════════════════════════════════════════════════════
#  ADD / EDIT USER DIALOG  (Admin only)
# ══════════════════════════════════════════════════════════════════════════════
class AddUserDialog(tk.Toplevel):
    """Admin dialog for creating a new user account."""

    def __init__(self, parent):
        super().__init__(parent)
        self.result = None
        self.title("Create User Account")
        self.resizable(False, False)
        self.configure(bg=BG1)
        self.transient(parent)
        self.grab_set()
        self._build()
        self.geometry(
            f"390x460+{parent.winfo_rootx()+100}+{parent.winfo_rooty()+80}"
        )
        self.wait_visibility()
        self.focus_force()

    def _build(self):
        f = tk.Frame(self, bg=BG1, padx=26, pady=22)
        f.pack(fill="both", expand=True)

        lbl(f, "Create User Account", 14, bold=True).pack(anchor="w", pady=(0, 20))

        # Name
        lbl(f, "Username *", 9, color=TXS).pack(anchor="w")
        self.v_name = tk.StringVar()
        entry_widget(f, self.v_name, width=30).pack(anchor="w", ipady=7, pady=(4, 14))

        # Password
        lbl(f, "Password *  (min 4 characters)", 9, color=TXS).pack(anchor="w")
        self.v_pw = tk.StringVar()
        entry_widget(f, self.v_pw, width=30, show="•").pack(anchor="w", ipady=7, pady=(4, 14))

        # Age + Gender row
        row = tk.Frame(f, bg=BG1)
        row.pack(fill="x", pady=(0, 14))

        af = tk.Frame(row, bg=BG1)
        af.pack(side="left", padx=(0, 24))
        lbl(af, "Age", 9, color=TXS).pack(anchor="w")
        self.v_age = tk.StringVar()
        entry_widget(af, self.v_age, width=7).pack(anchor="w", ipady=7, pady=(4, 0))

        gf = tk.Frame(row, bg=BG1)
        gf.pack(side="left")
        lbl(gf, "Gender", 9, color=TXS).pack(anchor="w")
        self.v_gender = tk.StringVar()
        gr = tk.Frame(gf, bg=BG1)
        gr.pack(pady=(6, 0))
        for g in ("Male", "Female", "Other"):
            tk.Radiobutton(gr, text=g, variable=self.v_gender, value=g,
                           font=(FNT, 9), bg=BG1, fg=TXP,
                           selectcolor=BG3, activebackground=BG1
                           ).pack(side="left", padx=(0, 8))

        # Role
        lbl(f, "Role", 9, color=TXS).pack(anchor="w", pady=(4, 0))
        self.v_role = tk.StringVar(value="user")
        rr = tk.Frame(f, bg=BG1)
        rr.pack(anchor="w", pady=(6, 18))
        tk.Radiobutton(rr, text="Regular User", variable=self.v_role, value="user",
                       font=(FNT, 10), bg=BG1, fg=GRN,
                       selectcolor=BG3, activebackground=BG1
                       ).pack(side="left", padx=(0, 16))
        tk.Radiobutton(rr, text="Admin", variable=self.v_role, value="admin",
                       font=(FNT, 10), bg=BG1, fg=PURP,
                       selectcolor=BG3, activebackground=BG1
                       ).pack(side="left")

        bf = tk.Frame(f, bg=BG1)
        bf.pack(fill="x")
        flat_btn(bf, "Cancel",           self.destroy, bg=BG3, fg=TXS).pack(side="left")
        flat_btn(bf, "  Create Account  ", self._submit, bg=ACC).pack(side="right")

    def _submit(self):
        name = self.v_name.get().strip()
        pw   = self.v_pw.get()
        if not name:
            messagebox.showerror("Error", "Username is required.", parent=self)
            return
        if len(pw) < 4:
            messagebox.showerror("Error", "Password must be at least 4 characters.", parent=self)
            return
        age = None
        if self.v_age.get().strip():
            try:
                age = int(self.v_age.get())
                assert 1 <= age <= 149
            except (ValueError, AssertionError):
                messagebox.showerror("Error", "Enter a valid age (1–149).", parent=self)
                return
        gender = self.v_gender.get() or None
        role   = self.v_role.get()
        try:
            uid = db.add_user(name, age, gender, pw, role)
            self.result = (uid, name, age, gender, role)
            self.destroy()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", f"Username '{name}' is already taken.", parent=self)


# ══════════════════════════════════════════════════════════════════════════════
#  BMI GAUGE CANVAS
# ══════════════════════════════════════════════════════════════════════════════
class GaugeCanvas(tk.Canvas):
    W, H      = 380, 205
    CX, CY    = 190, 200
    R_OUT     = 158
    R_IN      = 105
    TICK_BMIS = [10, 15, 20, 25, 30, 35, 40, 45]

    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG2)
        super().__init__(parent, width=self.W, height=self.H,
                         highlightthickness=0, **kw)
        self._draw_static()

    def _polar(self, r, deg):
        a = math.radians(deg)
        return self.CX + r * math.cos(a), self.CY - r * math.sin(a)

    def _arc_poly(self, r1, r2, a_start, a_end, color, n=32, **kw):
        for i in range(n):
            a1 = a_start + (a_end - a_start) * (i / n)
            a2 = a_start + (a_end - a_start) * ((i + 1) / n)
            xi1, yi1 = self._polar(r1, a1)
            xo1, yo1 = self._polar(r2, a1)
            xo2, yo2 = self._polar(r2, a2)
            xi2, yi2 = self._polar(r1, a2)
            self.create_polygon(xi1, yi1, xo1, yo1, xo2, yo2, xi2, yi2,
                                fill=color, outline="", **kw)

    def _draw_static(self):
        self._arc_poly(self.R_IN, self.R_OUT, 180, 0, BG3, n=56, tags="bg_track")
        for lo, hi, _, color in CATS:
            lo2 = max(float(lo), G_MIN)
            hi2 = min(float(hi), G_MAX)
            if lo2 >= hi2:
                continue
            self._arc_poly(self.R_IN + 5, self.R_OUT - 5,
                           bmi_to_angle(lo2), bmi_to_angle(hi2),
                           color, n=26, tags="cat_seg")
        for bmi_t in self.TICK_BMIS:
            a = bmi_to_angle(bmi_t)
            x1, y1 = self._polar(self.R_OUT, a)
            x2, y2 = self._polar(self.R_OUT + 11, a)
            self.create_line(x1, y1, x2, y2, fill=TXM, width=2, tags="ticks")
            xl, yl = self._polar(self.R_OUT + 23, a)
            self.create_text(xl, yl, text=str(bmi_t), fill=TXS,
                             font=(FNT, 7), tags="tick_lbl")
        self._redraw_inner_disc()
        self.create_text(self.CX, self.CY - 56, text="- -",
                         font=(FNT, 32, "bold"), fill=TXS, tags="val_txt")
        self.create_text(self.CX, self.CY - 22, text="BMI",
                         font=(FNT, 10), fill=TXS, tags="bmi_lbl")
        self.create_text(self.CX, self.CY - 4,
                         text="Enter values to calculate",
                         font=(FNT, 8), fill=TXM, tags="cat_txt")
        self._draw_pivot(TXM)

    def _redraw_inner_disc(self):
        self.delete("inner_disc")
        pts, n = [], 56
        for i in range(n + 1):
            x, y = self._polar(self.R_IN + 2, 180.0 - i * 180.0 / n)
            pts += [x, y]
        pts += [self.CX + self.R_IN + 2, self.CY,
                self.CX - self.R_IN - 2, self.CY]
        self.create_polygon(pts, fill=BG2, outline="", tags="inner_disc")

    def _draw_pivot(self, color=TXM):
        self.delete("pivot")
        r = 9
        self.create_oval(self.CX - r, self.CY - r,
                         self.CX + r, self.CY + r,
                         fill=color, outline=BG2, width=2, tags="pivot")

    def update_bmi(self, bmi: float):
        cat, color = get_cat(bmi)
        ang = bmi_to_angle(bmi)
        self.delete("needle")
        self._redraw_inner_disc()
        nx, ny = self._polar(self.R_IN - 8, ang)
        self.create_line(self.CX, self.CY, nx, ny,
                         fill=color, width=3, capstyle=tk.ROUND, tags="needle")
        self._draw_pivot(color)
        self.itemconfig("val_txt", text=f"{bmi:.1f}", fill=color)
        self.itemconfig("bmi_lbl", text="BMI", fill=TXS)
        self.itemconfig("cat_txt", text=cat, fill=color)
        for tag in ("inner_disc", "needle", "pivot", "val_txt", "bmi_lbl", "cat_txt"):
            self.tag_raise(tag)

    def reset(self):
        """Reset the gauge to its idle (no-data) state."""
        self.delete("needle")
        self._redraw_inner_disc()
        self._draw_pivot(TXM)
        self.itemconfig("val_txt", text="- -",                    fill=TXS)
        self.itemconfig("bmi_lbl", text="BMI",                    fill=TXS)
        self.itemconfig("cat_txt", text="No records yet",         fill=TXM)
        for tag in ("inner_disc", "pivot", "val_txt", "bmi_lbl", "cat_txt"):
            self.tag_raise(tag)


# ══════════════════════════════════════════════════════════════════════════════
#  DASHBOARD TAB
# ══════════════════════════════════════════════════════════════════════════════
class DashboardTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG0)
        self.app   = app
        self._last = None
        self._build()

    def _build(self):
        left = tk.Frame(self, bg=BG1, padx=28, pady=28, width=292)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        tk.Frame(self, bg=BDR, width=1).pack(side="left", fill="y")
        right = tk.Frame(self, bg=BG0)
        right.pack(side="left", fill="both", expand=True)

        lbl(left, "Calculate BMI", 17, bold=True).pack(anchor="w", pady=(0, 3))
        lbl(left, "Enter your measurements", 9, color=TXS).pack(anchor="w", pady=(0, 22))

        def field(parent, text, var):
            lbl(parent, text, 9, color=TXS).pack(anchor="w")
            e = entry_widget(parent, var, width=22)
            e.pack(anchor="w", ipady=8, pady=(4, 16))

        self.v_wt = tk.StringVar()
        self.v_ht = tk.StringVar()
        self.v_nt = tk.StringVar()
        field(left, "Weight  (kg)", self.v_wt)
        field(left, "Height  (m)",  self.v_ht)
        field(left, "Notes  (optional)", self.v_nt)

        flat_btn(left, "   Calculate BMI   ", self._calc, bg=ACC, size=12
                 ).pack(anchor="w", pady=(2, 0))
        tk.Frame(left, bg=BDR, height=1).pack(fill="x", pady=22)

        self.save_btn = flat_btn(left, "   Save Record   ", self._save,
                                 bg=GRN, fg="#0d1117", size=11)
        self.save_btn.pack(anchor="w")
        self.save_btn.config(state="disabled")

        # "Saving for:" context — shows whose record will be saved
        self.v_save_for = tk.StringVar(value="")
        self.save_for_lbl = tk.Label(
            left, textvariable=self.v_save_for,
            font=(FNT, 8, "bold"), fg=TEAL, bg=BG1
        )
        self.save_for_lbl.pack(anchor="w", pady=(5, 0))
        self.update_save_context()

        self.v_adv = tk.StringVar()
        self.adv_lbl = tk.Label(left, textvariable=self.v_adv, font=(FNT, 9),
                                fg=TXS, bg=BG1, wraplength=232, justify="left")
        self.adv_lbl.pack(anchor="w", pady=(14, 0))

        holder = tk.Frame(right, bg=BG0)
        holder.pack(expand=True)
        self.gauge = GaugeCanvas(holder)
        self.gauge.pack(pady=(20, 16))

        row = tk.Frame(holder, bg=BG0)
        row.pack(pady=(0, 6))
        self._res = []
        for title, unit in [("BMI Score", ""), ("Weight", "kg"), ("Height", "m")]:
            card = tk.Frame(row, bg=BG2, padx=20, pady=12)
            card.pack(side="left", padx=6)
            lbl(card, title, 8, color=TXS, bg=BG2).pack()
            vl = tk.Label(card, text="--", font=(FNT, 20, "bold"), fg=TXP, bg=BG2)
            vl.pack()
            lbl(card, unit, 8, color=TXS, bg=BG2).pack()
            self._res.append(vl)

        # ── Snapshot info bar (last record date + count) ───────────────────
        info_bar = tk.Frame(holder, bg=BG0)
        info_bar.pack(fill="x", padx=6, pady=(0, 10))

        self.v_last_ts    = tk.StringVar(value="")
        self.v_rec_count  = tk.StringVar(value="")

        self._last_ts_lbl = tk.Label(
            info_bar, textvariable=self.v_last_ts,
            font=(FNT, 8), fg=TXM, bg=BG0, anchor="w"
        )
        self._last_ts_lbl.pack(side="left")

        self._rec_count_lbl = tk.Label(
            info_bar, textvariable=self.v_rec_count,
            font=(FNT, 8, "bold"), fg=TEAL, bg=BG0, anchor="e"
        )
        self._rec_count_lbl.pack(side="right")

    def update_save_context(self):
        """Refresh the 'Saving for:' label whenever current_user changes."""
        cu = self.app.current_user
        if cu:
            is_admin = self.app.logged_in and self.app.logged_in[4] == "admin"
            prefix = "Saving for:" if is_admin else "Your record:"
            self.v_save_for.set(f"{prefix}  {cu[1]}")
        else:
            self.v_save_for.set("")

    def refresh_snapshot(self):
        """
        Load the most recent BMI record for the currently selected user
        and display it on the gauge + cards.  Called whenever the active
        user changes (admin switching users) or after a new record is saved.
        """
        cu = self.app.current_user
        if not cu:
            self.gauge.reset()
            for r in self._res:
                r.config(text="--", fg=TXP)
            self.v_adv.set("")
            self.v_last_ts.set("")
            self.v_rec_count.set("")
            return

        records = db.get_records(cu[0])   # sorted newest-first
        count   = len(records)

        if count == 0:
            self.gauge.reset()
            for r in self._res:
                r.config(text="--", fg=TXP)
            self.v_adv.set("Select a user or enter values to calculate.")
            self.adv_lbl.config(fg=TXS)
            self.v_last_ts.set("No records yet")
            self.v_rec_count.set("")
            # Reset save state so admin cannot accidentally save stale data
            self._last = None
            self.save_btn.config(state="disabled")
            return

        # ── Populate from most recent record ──────────────────────────────
        _rid, w, h, bmi, cat, _notes, ts = records[0]
        _, color = get_cat(bmi)

        self.gauge.update_bmi(bmi)
        self._res[0].config(text=f"{bmi:.1f}", fg=color)
        self._res[1].config(text=f"{w:.1f}")
        self._res[2].config(text=f"{h:.2f}")
        self.v_adv.set(ADVICE.get(cat, ""))
        self.adv_lbl.config(fg=color)
        self.v_last_ts.set(f"Last record: {ts}")
        self.v_rec_count.set(f"{count} record{'s' if count != 1 else ''} total")

        # Reset so Save button requires a fresh calculation before enabling
        self._last = None
        self.save_btn.config(state="disabled")


    def _calc(self):
        try:
            w = float(self.v_wt.get())
            assert 1 <= w <= 700
        except (ValueError, AssertionError):
            messagebox.showerror("Invalid Input", "Enter a valid weight (1–700 kg).")
            return
        try:
            h = float(self.v_ht.get())
            assert 0.5 <= h <= 3.0
        except (ValueError, AssertionError):
            messagebox.showerror("Invalid Input", "Enter a valid height (0.5–3.0 m).")
            return
        bmi = w / (h * h)
        cat, color = get_cat(bmi)
        self.gauge.update_bmi(bmi)
        self._res[0].config(text=f"{bmi:.1f}", fg=color)
        self._res[1].config(text=f"{w:.1f}")
        self._res[2].config(text=f"{h:.2f}")
        self.v_adv.set(ADVICE.get(cat, ""))
        self.adv_lbl.config(fg=color)
        self._last = (w, h, bmi, cat)
        self.save_btn.config(state="normal")

    def _save(self):
        if not self.app.current_user:
            messagebox.showwarning("No User", "Please select a user first.")
            return
        if not self._last:
            return
        w, h, bmi, cat = self._last
        db.add_record(self.app.current_user[0], w, h, bmi, cat,
                      self.v_nt.get().strip())
        name = self.app.current_user[1]
        messagebox.showinfo("Saved", f"BMI {bmi:.1f} ({cat}) saved for {name}.")
        self.save_btn.config(state="disabled")
        self.app.on_data_change()


# ══════════════════════════════════════════════════════════════════════════════
#  HISTORY TAB
# ══════════════════════════════════════════════════════════════════════════════
class HistoryTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG0)
        self.app  = app
        self._ids = []
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG0, padx=28, pady=20)
        hdr.pack(fill="x")
        lbl(hdr, "BMI History", 17, bold=True).pack(side="left")
        # ── Delete button: Admin only ──────────────────────────────────────
        if self.app.logged_in and self.app.logged_in[4] == "admin":
            flat_btn(hdr, "  Delete Selected  ", self._delete,
                     bg="#3d1f1f", fg=RED).pack(side="right")
        else:
            lbl(hdr, "View-only  ·  Contact admin to delete records",
                9, color=TXM).pack(side="right", padx=4)
        hdiv(self)

        tf = tk.Frame(self, bg=BG0, padx=28, pady=16)
        tf.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("H.Treeview", background=BG2, foreground=TXP,
                        rowheight=42, fieldbackground=BG2,
                        borderwidth=0, font=(FNT, 10))
        style.configure("H.Treeview.Heading", background=BG1, foreground=TXS,
                        font=(FNT, 9, "bold"), relief="flat")
        style.map("H.Treeview",
                  background=[("selected", BG3)], foreground=[("selected", TXP)])

        cols = ("ts", "weight", "height", "bmi", "cat", "notes")
        self.tree = ttk.Treeview(tf, columns=cols, show="headings",
                                  style="H.Treeview", selectmode="browse")
        for col, head, w, anc in [
            ("ts",     "Date & Time",  158, "center"),
            ("weight", "Weight (kg)",  105, "center"),
            ("height", "Height (m)",   105, "center"),
            ("bmi",    "BMI",           82, "center"),
            ("cat",    "Category",     162, "center"),
            ("notes",  "Notes",        200, "w"),
        ]:
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor=anc)

        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        for _, _, cat, color in CATS:
            self.tree.tag_configure(cat, foreground=color)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self._ids = []
        if not self.app.current_user:
            return
        for rid, w, h, bmi, cat, notes, ts in db.get_records(self.app.current_user[0]):
            self.tree.insert("", "end", tags=(cat,),
                values=(ts, f"{w:.1f}", f"{h:.2f}", f"{bmi:.2f}", cat, notes or ""))
            self._ids.append(rid)

    def _delete(self):
        # ── Admin-only guard ───────────────────────────────────────────────
        if not self.app.logged_in or self.app.logged_in[4] != "admin":
            messagebox.showerror(
                "Access Denied",
                "Only an admin can delete BMI records.\n"
                "Please contact your administrator."
            )
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a Record", "Click a row to select it first.")
            return
        if messagebox.askyesno("Confirm Delete", "Permanently delete this record?"):
            db.del_record(self._ids[self.tree.index(sel[0])])
            self.refresh()
            self.app.analysis_tab.refresh()


# ══════════════════════════════════════════════════════════════════════════════
#  ANALYSIS TAB
# ══════════════════════════════════════════════════════════════════════════════
class AnalysisTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG0)
        self.app        = app
        self._mpl       = None
        self._empty_lbl = None
        self._build()

    def _build(self):
        hdr = tk.Frame(self, bg=BG0, padx=28, pady=20)
        hdr.pack(fill="x")
        lbl(hdr, "BMI Analysis", 17, bold=True).pack(side="left")
        hdiv(self)

        sf = tk.Frame(self, bg=BG0, padx=28, pady=16)
        sf.pack(fill="x")
        self._stat_lbls = {}
        for key, title, color in [
            ("count",   "Total Records", TEAL),
            ("bmi_avg", "Average BMI",   ACC ),
            ("bmi_min", "Minimum BMI",   GRN ),
            ("bmi_max", "Maximum BMI",   ORG ),
        ]:
            card = tk.Frame(sf, bg=BG2, padx=22, pady=12)
            card.pack(side="left", padx=(0, 12))
            lbl(card, title, 9, color=TXS, bg=BG2).pack()
            vl = tk.Label(card, text="--", font=(FNT, 22, "bold"), fg=color, bg=BG2)
            vl.pack()
            self._stat_lbls[key] = vl

        hdiv(self, pady=(8, 0))
        self.chart_area = tk.Frame(self, bg=BG0, padx=28, pady=12)
        self.chart_area.pack(fill="both", expand=True)
        if not HAS_MPL:
            tk.Label(self.chart_area,
                text="Install matplotlib to enable charts:\n\n    pip install matplotlib",
                font=(FNT, 11), fg=TXS, bg=BG0, justify="center"
            ).pack(expand=True)

    def refresh(self):
        if not self.app.current_user:
            return
        uid   = self.app.current_user[0]
        stats = db.get_stats(uid)
        if stats:
            self._stat_lbls["count"].config(text=str(stats["count"]))
            self._stat_lbls["bmi_avg"].config(text=f"{stats['bmi_avg']:.1f}")
            self._stat_lbls["bmi_min"].config(text=f"{stats['bmi_min']:.1f}")
            self._stat_lbls["bmi_max"].config(text=f"{stats['bmi_max']:.1f}")
        else:
            for v in self._stat_lbls.values():
                v.config(text="--")
        if HAS_MPL:
            self._draw_charts(uid)

    def _draw_charts(self, uid):
        if self._mpl:
            self._mpl.get_tk_widget().destroy()
            self._mpl = None
        if self._empty_lbl and self._empty_lbl.winfo_exists():
            self._empty_lbl.destroy()
            self._empty_lbl = None

        ts_list, bmi_list, _ = db.get_trend(uid)
        if len(bmi_list) < 2:
            self._empty_lbl = tk.Label(
                self.chart_area,
                text="Add at least 2 BMI records to see trend charts.",
                font=(FNT, 11), fg=TXS, bg=BG0
            )
            self._empty_lbl.pack(expand=True)
            return

        dates = []
        for t in ts_list:
            try:
                dates.append(datetime.datetime.strptime(t, "%Y-%m-%d %H:%M:%S"))
            except ValueError:
                dates.append(datetime.datetime.now())

        fig = Figure(figsize=(9.2, 4.2), dpi=90, facecolor=BG0)

        ax1 = fig.add_subplot(1, 2, 1)
        ax1.set_facecolor(BG2)
        y_lo = max(0,  min(bmi_list) - 4)
        y_hi = min(50, max(bmi_list) + 4)
        for lo, hi, col, alpha in [
            (0,    16,   "#ef4444", .08), (16,   18.5, CYN, .08),
            (18.5, 25,   GRN,       .12), (25,   30,   YEL, .08),
            (30,   35,   ORG,       .08), (35,   40,   RED, .08),
            (40,   50,   "#dc2626", .08),
        ]:
            ax1.axhspan(max(lo, y_lo), min(hi, y_hi), alpha=alpha, color=col, linewidth=0)
        ax1.axhline(18.5, color=GRN, ls="--", lw=0.9, alpha=0.55)
        ax1.axhline(25,   color=GRN, ls="--", lw=0.9, alpha=0.55)
        ax1.plot(dates, bmi_list, color=ACC, lw=2.2, zorder=5)
        ax1.scatter(dates, bmi_list, color=TEAL, s=48, zorder=6)
        ax1.set_ylim(y_lo, y_hi)
        ax1.set_xlabel("Date", color=TXS, fontsize=9)
        ax1.set_ylabel("BMI",  color=TXS, fontsize=9)
        ax1.set_title("BMI Trend Over Time", color=TXP, fontsize=11, fontweight="bold", pad=10)
        ax1.tick_params(colors=TXS, labelsize=8)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax1.xaxis.set_major_locator(mdates.AutoDateLocator())
        for s in ax1.spines.values():
            s.set_color(BDR)
        ax1.grid(axis="y", color=BDR, lw=0.5, alpha=0.4)
        fig.autofmt_xdate(rotation=25, ha="right")

        ax2 = fig.add_subplot(1, 2, 2)
        ax2.set_facecolor(BG2)
        cat_count = {c: 0 for _, _, c, _ in CATS}
        for _, _, _, bmi, cat, _, _ in db.get_records(uid):
            if cat in cat_count:
                cat_count[cat] += 1
        labels = [k for k, v in cat_count.items() if v > 0]
        counts = [cat_count[k] for k in labels]
        colors = [next(c for _, _, n, c in CATS if n == k) for k in labels]
        if labels:
            _, _, autos = ax2.pie(counts, labels=None, autopct="%1.0f%%",
                                  colors=colors, startangle=90,
                                  wedgeprops={"linewidth": 2.5, "edgecolor": BG0},
                                  pctdistance=0.80)
            for at in autos:
                at.set_color(BG0)
                at.set_fontsize(9)
                at.set_fontweight("bold")
            ax2.legend(labels, loc="lower center", ncol=2, fontsize=7.5,
                       facecolor=BG1, labelcolor=TXP, edgecolor=BDR,
                       bbox_to_anchor=(0.5, -0.28))
        ax2.set_title("Category Distribution", color=TXP, fontsize=11,
                      fontweight="bold", pad=10)
        fig.tight_layout(pad=2.5)

        canvas = FigureCanvasTkAgg(fig, master=self.chart_area)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        self._mpl = canvas


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD TAB
# ══════════════════════════════════════════════════════════════════════════════
class AdminDashboardTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG0)
        self.app = app
        self._build()

    def _build(self):
        # Header
        hdr = tk.Frame(self, bg=BG0, padx=28, pady=20)
        hdr.pack(fill="x")
        lbl(hdr, "Admin Dashboard - All Users Summary", 17, bold=True).pack(side="left")
        hdiv(self)

        # Stats Cards Row
        self.stats_frame = tk.Frame(self, bg=BG0, padx=28, pady=16)
        self.stats_frame.pack(fill="x")
        
        self._stat_lbls = {}
        for key, title, color in [
            ("users",     "Total Users",     TEAL),
            ("records",   "Total Records",   ACC ),
            ("avg_bmi",   "Global Avg BMI",  GRN ),
            ("healthy_p", "Healthy Weight %",YEL ),
        ]:
            card = tk.Frame(self.stats_frame, bg=BG2, padx=22, pady=12)
            card.pack(side="left", padx=(0, 12), expand=True, fill="x")
            lbl(card, title, 9, color=TXS, bg=BG2).pack()
            vl = tk.Label(card, text="--", font=(FNT, 22, "bold"), fg=color, bg=BG2)
            vl.pack()
            self._stat_lbls[key] = vl

        hdiv(self)

        # Main Area: Left (Treeview), Right (Quick Actions)
        main_area = tk.Frame(self, bg=BG0, padx=28, pady=16)
        main_area.pack(fill="both", expand=True)

        left_f = tk.Frame(main_area, bg=BG0)
        left_f.pack(side="left", fill="both", expand=True)

        right_f = tk.Frame(main_area, bg=BG1, padx=20, pady=20, width=200)
        right_f.pack(side="right", fill="y", padx=(20, 0))
        right_f.pack_propagate(False)

        # Table style (same as HistoryTab)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("A.Treeview", background=BG2, foreground=TXP,
                        rowheight=40, fieldbackground=BG2,
                        borderwidth=0, font=(FNT, 10))
        style.configure("A.Treeview.Heading", background=BG1, foreground=TXS,
                        font=(FNT, 9, "bold"), relief="flat")
        style.map("A.Treeview",
                  background=[("selected", BG3)], foreground=[("selected", TXP)])

        cols = ("name", "role", "age", "gender", "count", "bmi", "cat", "last_active")
        self.tree = ttk.Treeview(left_f, columns=cols, show="headings",
                                  style="A.Treeview", selectmode="browse")
        
        for col, head, w, anc in [
            ("name",        "Username",      120, "w"),
            ("role",        "Role",           80, "center"),
            ("age",         "Age",            60, "center"),
            ("gender",      "Gender",         80, "center"),
            ("count",       "Logs Count",     100, "center"),
            ("bmi",         "Latest BMI",     90, "center"),
            ("cat",         "Category",      130, "center"),
            ("last_active", "Last Updated",  150, "center"),
        ]:
            self.tree.heading(col, text=head)
            self.tree.column(col, width=w, anchor=anc)

        vsb = ttk.Scrollbar(left_f, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Color config
        for _, _, cat, color in CATS:
            self.tree.tag_configure(cat, foreground=color)
        self.tree.tag_configure("admin", foreground=PURP)
        self.tree.tag_configure("user", foreground=TXP)

        # Quick Actions
        lbl(right_f, "Quick Actions", 12, bold=True, bg=BG1).pack(anchor="w", pady=(0, 15))
        
        flat_btn(right_f, "View Dashboard", lambda: self._view_user("dashboard"), bg=ACC, fg=TXP).pack(fill="x", pady=5)
        flat_btn(right_f, "View History", lambda: self._view_user("history"), bg=ACC, fg=TXP).pack(fill="x", pady=5)
        flat_btn(right_f, "View Analysis", lambda: self._view_user("analysis"), bg=ACC, fg=TXP).pack(fill="x", pady=5)
        
        tk.Frame(right_f, bg=BDR, height=1).pack(fill="x", pady=15)
        
        flat_btn(right_f, "+ Add User", self.app._add_user, bg=GRN, fg="#0d1117").pack(fill="x", pady=5)
        flat_btn(right_f, "- Remove User", self.app._del_user, bg="#2d1515", fg=RED).pack(fill="x", pady=5)

        # Double click to view dashboard
        self.tree.bind("<Double-1>", lambda _: self._view_user("dashboard"))
        # Single click selection updates active user context
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

    def refresh(self):
        """Refresh all statistics and list of users."""
        self.tree.delete(*self.tree.get_children())
        self._user_map = {}
        
        summary = self._get_all_users_data()
        
        total_users = len(summary)
        total_records = 0
        sum_latest_bmi = 0.0
        active_users_count = 0
        healthy_users_count = 0
        
        for idx, (uid, name, age, gender, role, count, latest) in enumerate(summary):
            total_records += count
            bmi_val = "--"
            cat_val = "--"
            ts_val = "--"
            row_tags = []
            
            if latest:
                w, h, bmi, cat, ts = latest
                bmi_val = f"{bmi:.1f}"
                cat_val = cat
                ts_val = ts
                sum_latest_bmi += bmi
                active_users_count += 1
                if 18.5 <= bmi < 25.0:
                    healthy_users_count += 1
                row_tags.append(cat)
            else:
                row_tags.append(role)
                
            self.tree.insert("", "end", iid=str(idx), tags=tuple(row_tags),
                values=(name, role.capitalize(), age or "--", gender or "--", count, bmi_val, cat_val, ts_val))
            
            # Map index to user tuple so we can switch easily
            self._user_map[str(idx)] = (uid, name, age, gender, role)

        # Update stats cards
        self._stat_lbls["users"].config(text=str(total_users))
        self._stat_lbls["records"].config(text=str(total_records))
        
        avg_bmi = sum_latest_bmi / active_users_count if active_users_count > 0 else 0.0
        self._stat_lbls["avg_bmi"].config(text=f"{avg_bmi:.1f}" if active_users_count > 0 else "--")
        
        healthy_p = (healthy_users_count / active_users_count * 100) if active_users_count > 0 else 0.0
        self._stat_lbls["healthy_p"].config(text=f"{healthy_p:.0f}%" if active_users_count > 0 else "--")

    def _get_all_users_data(self):
        with db._cx() as c:
            users = c.execute("SELECT id, name, age, gender, role FROM users WHERE role='user' ORDER BY name").fetchall()
            summary = []
            for uid, name, age, gender, role in users:
                latest = c.execute(
                    "SELECT weight, height, bmi, cat, ts FROM records "
                    "WHERE uid=? ORDER BY ts DESC LIMIT 1", (uid,)
                ).fetchone()
                count = c.execute("SELECT COUNT(*) FROM records WHERE uid=?", (uid,)).fetchone()[0]
                summary.append((uid, name, age, gender, role, count, latest))
            return summary

    def _view_user(self, tab_key):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select User", "Click a user from the list first.")
            return
        
        user_tuple = self._user_map.get(sel[0])
        if user_tuple:
            # Update active user in App combobox and switch
            name_to_find = user_tuple[1]
            display_names = self.app.user_cb["values"]
            
            for i, val in enumerate(display_names):
                # Clean the val (remove ' ★' for admin)
                clean_val = val.replace(" ★", "").strip()
                if clean_val == name_to_find:
                    self.app.user_cb.current(i)
                    self.app._select_user_tuple(self.app._user_list[i])
                    break
            
            # Switch to requested tab
            self.app._show_tab(tab_key)

    def _on_row_select(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        user_tuple = self._user_map.get(sel[0])
        if user_tuple:
            name_to_find = user_tuple[1]
            display_names = self.app.user_cb["values"]
            for i, val in enumerate(display_names):
                clean_val = val.replace(" ★", "").strip()
                if clean_val == name_to_find:
                    self.app.user_cb.current(i)
                    self.app._select_user_tuple(self.app._user_list[i])
                    break


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION WINDOW
# ══════════════════════════════════════════════════════════════════════════════
class App(tk.Tk):
    """
    Root window.
    Starts with the LoginFrame; after authentication switches to the main UI.
    Role-based access:
      • admin → full user management, can view any user's data
      • user  → locked to their own data, no user management
    """

    def __init__(self):
        super().__init__()
        self.title("BMI Tracker Pro")
        self.geometry("520x480")
        self.resizable(False, False)
        self.configure(bg=BG0)

        self.logged_in    = None   # (id, name, age, gender, role) — authenticated session
        self.current_user = None   # (id, name, age, gender)        — whose data is shown
        self._user_list   = []     # admin only: list of all users
        self._active_tab  = None

        # Show login screen first
        self._login_frame = LoginFrame(self, self._after_login)
        self._login_frame.pack(fill="both", expand=True)

    # ── Authentication flow ───────────────────────────────────────────────
    def _after_login(self, user_row):
        """Called by LoginFrame after successful authentication."""
        self.logged_in = user_row   # (id, name, age, gender, role)
        self._login_frame.destroy()
        self._login_frame = None

        # Resize to full app
        self.resizable(True, True)
        self.geometry("1200x740")
        self.minsize(920, 600)

        self._build_main()

    def _logout(self):
        if not messagebox.askyesno("Log Out", "Are you sure you want to log out?"):
            return
        # Tear down the main layout
        for widget in self.winfo_children():
            widget.destroy()
        # Reset state
        self.logged_in    = None
        self.current_user = None
        self._user_list   = []
        self._active_tab  = None
        # Resize back to login
        self.geometry("520x480")
        self.resizable(False, False)
        # Show login screen again
        self._login_frame = LoginFrame(self, self._after_login)
        self._login_frame.pack(fill="both", expand=True)

    # ── Main UI builder ───────────────────────────────────────────────────
    def _build_main(self):
        is_admin = self.logged_in[4] == "admin"

        # ── Header ────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG1, height=58)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Left: logo
        logo_row = tk.Frame(hdr, bg=BG1)
        logo_row.pack(side="left", padx=16, pady=10)
        tk.Label(logo_row, text="BMI Tracker Pro",
                 font=(FNT, 14, "bold"), fg=ACC, bg=BG1).pack(side="left")
        if is_admin:
            tk.Label(logo_row, text="  ADMIN",
                     font=(FNT, 9, "bold"), fg=PURP, bg=BG1).pack(side="left", pady=2)

        # Right: user selector (admin) or "logged in as" label (user)
        right_hdr = tk.Frame(hdr, bg=BG1)
        right_hdr.pack(side="right", padx=16)

        if is_admin:
            tk.Label(right_hdr, text="Viewing:", font=(FNT, 9), fg=TXS, bg=BG1
                     ).pack(side="left", padx=(0, 6))
            style = ttk.Style()
            style.configure("U.TCombobox", fieldbackground=BG3, background=BG3,
                            foreground=TXP, selectbackground=BG3, selectforeground=TXP)
            self.v_user = tk.StringVar()
            self.user_cb = ttk.Combobox(right_hdr, textvariable=self.v_user,
                                         state="readonly", width=22,
                                         font=(FNT, 10), style="U.TCombobox")
            self.user_cb.pack(side="left")
            self.user_cb.bind("<<ComboboxSelected>>", self._on_user_change)
        else:
            tk.Label(right_hdr, text=f"Logged in as:",
                     font=(FNT, 9), fg=TXS, bg=BG1).pack(side="left", padx=(0, 4))
            tk.Label(right_hdr, text=self.logged_in[1],
                     font=(FNT, 10, "bold"), fg=TXP, bg=BG1).pack(side="left")

        tk.Frame(self, bg=BDR, height=1).pack(fill="x")

        # ── Body ──────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG0)
        body.pack(fill="both", expand=True)

        sb = tk.Frame(body, bg=BG1, width=195)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)
        tk.Frame(body, bg=BDR, width=1).pack(side="left", fill="y")

        self.content = tk.Frame(body, bg=BG0)
        self.content.pack(side="left", fill="both", expand=True)

        # ── Sidebar ───────────────────────────────────────────────────────
        # User profile card
        uc = tk.Frame(sb, bg=BG2, padx=14, pady=14)
        uc.pack(fill="x", padx=12, pady=(18, 6))

        # Role badge color
        badge_bg = PURP if is_admin else ACC
        self.avatar = tk.Label(uc, text="?", font=(FNT, 18, "bold"),
                               fg=BG0, bg=badge_bg, width=3, height=1)
        self.avatar.pack()
        self.name_lbl = tk.Label(uc, text="...",
                                  font=(FNT, 10, "bold"), fg=TXP, bg=BG2, wraplength=155)
        self.name_lbl.pack(pady=(8, 2))
        self.info_lbl = tk.Label(uc, text="", font=(FNT, 8), fg=TXS, bg=BG2)
        self.info_lbl.pack()

        hdiv(sb)

        # Buttons row — Admin: add/delete user | Regular user: change password
        bf = tk.Frame(sb, bg=BG1, padx=12)
        bf.pack(fill="x", pady=4)

        if is_admin:
            self._sb_btn(bf, "  + Add User",    self._add_user,    BG3,      TXP ).pack(fill="x", pady=2)
            self._sb_btn(bf, "  - Remove User",  self._del_user,    "#2d1515", RED ).pack(fill="x", pady=2)
        else:
            self._sb_btn(bf, "  Change Password",
                         lambda: ChangePasswordDialog(self, self.logged_in[0], self.logged_in[1]),
                         BG3, TEAL).pack(fill="x", pady=2)

        hdiv(sb)

        # Navigation
        tk.Label(sb, text="VIEWS", font=(FNT, 8, "bold"),
                 fg=TXM, bg=BG1).pack(anchor="w", padx=16, pady=(4, 4))
        
        nav_items = []
        if is_admin:
            nav_items.append(("admin_dashboard", "☷", "   Admin Dashboard"))
        nav_items.extend([
            ("dashboard", "□", "   Dashboard"),
            ("history",   "≡", "   History"),
            ("analysis",  "∆", "   Analysis"),
        ])
        
        self.nav_btns = {}
        for key, icon, text in nav_items:
            b = tk.Button(
                sb, text=f"  {icon}  {text}", font=(FNT, 11),
                fg=TXS, bg=BG1, activebackground=BG3, activeforeground=TXP,
                relief="flat", bd=0, padx=10, pady=11, anchor="w", cursor="hand2",
                command=lambda k=key: self._show_tab(k)
            )
            b.pack(fill="x", padx=6)
            b.bind("<Enter>",
                   lambda e, btn=b, k=key: btn.config(bg=BG3)
                   if k != self._active_tab else None)
            b.bind("<Leave>",
                   lambda e, btn=b, k=key:
                   btn.config(bg=BG3 if k == self._active_tab else BG1))
            self.nav_btns[key] = b

        # Logout button at sidebar bottom
        hdiv(sb)
        self._sb_btn(sb, "  ⏻  Log Out", self._logout, "#1e1414", RED
                     ).pack(fill="x", padx=12, pady=6)

        # ── Status bar ────────────────────────────────────────────────────
        self.v_status = tk.StringVar(value="Welcome back!")
        tk.Label(self, textvariable=self.v_status,
                 font=(FNT, 9), fg=TXS, bg=BG1,
                 anchor="w", padx=16, pady=5).pack(side="bottom", fill="x")
        tk.Frame(self, bg=BDR, height=1).pack(side="bottom", fill="x")

        # ── Tabs ──────────────────────────────────────────────────────────
        if is_admin:
            self.admin_dashboard_tab = AdminDashboardTab(self.content, self)
        self.dashboard_tab = DashboardTab(self.content, self)
        self.history_tab   = HistoryTab(self.content, self)
        self.analysis_tab  = AnalysisTab(self.content, self)

        # ── Initial data load ─────────────────────────────────────────────
        self._load_users_or_self()
        if is_admin:
            self._show_tab("admin_dashboard")
        else:
            self._show_tab("dashboard")

    # ── Data loading ──────────────────────────────────────────────────────
    def _load_users_or_self(self):
        """Admin loads all users; regular user locks to themselves."""
        is_admin = self.logged_in[4] == "admin"
        if is_admin:
            # Show only regular users in the list for the admin
            self._user_list = [u for u in db.get_users() if u[4] == "user"]
            display = [u[1] for u in self._user_list]
            self.user_cb["values"] = display
            if self._user_list:
                self.user_cb.current(0)
                self._select_user_tuple(self._user_list[0])
            else:
                self._select_user_tuple(None)
        else:
            # Regular user: locked to their own account
            self._select_user_tuple(self.logged_in)   # first 4 fields used as current_user

    def _on_user_change(self, _=None):
        idx = self.user_cb.current()
        if 0 <= idx < len(self._user_list):
            self._select_user_tuple(self._user_list[idx])
            if self._active_tab == "admin_dashboard":
                self._show_tab("dashboard")

    def _select_user_tuple(self, user):
        """Update current_user and refresh sidebar card."""
        is_admin = self.logged_in[4] == "admin"
        if not user:
            self.current_user = None
            self.avatar.config(text="?")
            self.name_lbl.config(text="No Users")
            self.info_lbl.config(text="")
            if hasattr(self, "v_status"):
                self.v_status.set("Viewing: No User Selected" if is_admin else "Welcome!")
            self.on_data_change()
            if hasattr(self, "dashboard_tab"):
                self.dashboard_tab.update_save_context()
                self.dashboard_tab.refresh_snapshot()
            return

        # user is (id, name, age, gender[, role])
        uid, name, age, gender = user[0], user[1], user[2], user[3]
        self.current_user = (uid, name, age, gender)

        self.avatar.config(text=name[0].upper())
        self.name_lbl.config(text=name)
        parts = []
        if age:    parts.append(f"Age {age}")
        if gender: parts.append(gender)
        # Show role badge for admin panel
        if is_admin and len(user) > 4:
            role_txt = " · Admin ★" if user[4] == "admin" else " · User"
            parts.append(role_txt)
        self.info_lbl.config(text="  ·  ".join(parts) if parts else "BMI User")

        if hasattr(self, "v_status"):
            who = f"Viewing data for: {name}" if is_admin else f"Welcome, {name}"
            self.v_status.set(who)
        self.on_data_change()
        # Keep Dashboard labels in sync with the newly selected user
        if hasattr(self, "dashboard_tab"):
            self.dashboard_tab.update_save_context()
            self.dashboard_tab.refresh_snapshot()

    # ── Tab control ───────────────────────────────────────────────────────
    def _show_tab(self, key: str):
        self._active_tab = key
        for t in (self.dashboard_tab, self.history_tab, self.analysis_tab):
            t.pack_forget()
        if hasattr(self, "admin_dashboard_tab"):
            self.admin_dashboard_tab.pack_forget()

        if key == "admin_dashboard" and hasattr(self, "admin_dashboard_tab"):
            self.admin_dashboard_tab.pack(fill="both", expand=True)
            self.admin_dashboard_tab.refresh()
        else:
            {"dashboard": self.dashboard_tab,
             "history":   self.history_tab,
             "analysis":  self.analysis_tab}[key].pack(fill="both", expand=True)

        for k, b in self.nav_btns.items():
            b.config(bg=BG3 if k == key else BG1,
                     fg=TXP if k == key else TXS,
                     font=(FNT, 11, "bold" if k == key else "normal"))

        if key == "history":
            self.history_tab.refresh()
        elif key == "analysis":
            self.analysis_tab.refresh()
        elif key == "dashboard":
            # Refresh snapshot so the gauge shows the latest record
            self.dashboard_tab.refresh_snapshot()

    def on_data_change(self):
        if self._active_tab == "history":
            self.history_tab.refresh()
        elif self._active_tab == "analysis":
            self.analysis_tab.refresh()
        elif self._active_tab == "dashboard":
            # After saving a new record, refresh the snapshot on the dashboard
            self.dashboard_tab.refresh_snapshot()

    # ── Admin user management ─────────────────────────────────────────────
    def _sb_btn(self, parent, text, cmd, bg, fg):
        b = flat_btn(parent, text, cmd, bg=bg, fg=fg, size=9)
        return b

    def _add_user(self):
        dlg = AddUserDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            uid, name, age, gender, role = dlg.result
            self._user_list = [u for u in db.get_users() if u[4] == "user"]
            display = [u[1] for u in self._user_list]
            self.user_cb["values"] = display
            if role == "user":
                names = [u[1] for u in self._user_list]
                idx = names.index(name)
                self.user_cb.current(idx)
                self._select_user_tuple(self._user_list[idx])
            else:
                # If admin created another admin, keep the active selection as is
                if self._user_list:
                    # Refresh active selection if available
                    pass
            self.v_status.set(f"Account '{name}' ({role}) created.")
            if hasattr(self, "admin_dashboard_tab"):
                self.admin_dashboard_tab.refresh()

    def _del_user(self):
        if not self.current_user:
            messagebox.showinfo("No User", "Select a user first.")
            return
        uid, name = self.current_user[0], self.current_user[1]
        # Prevent admin deleting their own account
        if uid == self.logged_in[0]:
            messagebox.showerror("Cannot Delete",
                                 "You cannot delete your own admin account.")
            return
        if messagebox.askyesno(
            "Delete Account",
            f"Permanently delete '{name}' and ALL their BMI records?\n"
            "This cannot be undone."
        ):
            db.del_user(uid)
            self._user_list = [u for u in db.get_users() if u[4] == "user"]
            display = [u[1] for u in self._user_list]
            self.user_cb["values"] = display
            if self._user_list:
                self.user_cb.current(0)
                self._select_user_tuple(self._user_list[0])
            else:
                self._select_user_tuple(None)
            self.v_status.set(f"Account '{name}' deleted.")
            if hasattr(self, "admin_dashboard_tab"):
                self.admin_dashboard_tab.refresh()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    App().mainloop()

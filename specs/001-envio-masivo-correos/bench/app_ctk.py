import sys

import customtkinter as ctk

app = ctk.CTk()
ctk.CTkButton(app, text="ok").pack()
app.after(1500, app.destroy)
app.mainloop()
print("CTK_OK", file=sys.stderr)

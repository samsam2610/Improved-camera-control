import tkinter as tk
from tkinter import StringVar

root = tk.Tk()
#Now you want another frame
for i in range(5):
    gridframe = tk.Frame(root)
    tk.Label(gridframe, text='Top').grid(row=0, column=0)
    tk.Entry(gridframe, textvariable=StringVar(), width=5).grid(row=0, column=1)

    tk.Label(gridframe, text='Left').grid(row=0, column=2)
    tk.Entry(gridframe, textvariable=StringVar(), width=5).grid(row=0, column=3)

    tk.Label(gridframe, text='Height').grid(row=1, column=0)
    tk.Entry(gridframe, textvariable=StringVar(), width=5).grid(row=1, column=1)

    tk.Label(gridframe, text='Width').grid(row=1, column=2)
    tk.Entry(gridframe, textvariable=StringVar(),  width=5).grid(row=1, column=3)

    gridframe.grid(row=0, column=i, padx=20)
root.mainloop()

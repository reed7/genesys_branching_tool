"""
Performance is awful
"""
from Tkinter import *


class MyProgressBar(Canvas):

    def __init__(self, width=560, height=30, color="blue", outline_color="blue", bd=0):
        Canvas.__init__(self, width=width, height=height, bd=bd)

        self.progress_bar_width = width
        self.progress_bar_color = color
        self.outline_color = outline_color

        self.__current_progress = 0
        self.__total_unit = 1
        self.__tmp_bar = None

    def refresh_bar_by_unit(self, unit=1):
        self.__current_progress += self.progress_bar_width * float(unit) / self.__total_unit
        self.delete(self.__tmp_bar)
        self.__tmp_bar = \
            self.create_rectangle(0, 0, self.__current_progress, 25, fill=self.progress_bar_color, outline=self.outline_color)

    def init_progress(self, total_unit=1):
        self.__current_progress = 0
        self.__total_unit = total_unit
        self.delete(ALL)

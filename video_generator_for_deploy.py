import os
import tkinter as tk
from tkinter import ttk
from tkinter import PhotoImage, filedialog, messagebox
from moviepy.editor import *
from moviepy.editor import TextClip, ImageClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip
from moviepy.video.tools.subtitles import file_to_subtitles
# from pathlib import Path
import re
import traceback
from PIL import Image, ImageTk, ImageSequence
import tempfile
import json
import auto_vrew
import numpy as np
from moviepy.video.io.bindings import PIL_to_npimage
from PIL import Image
import threading
from proglog import ProgressBarLogger
from moviepy.video.fx.all import loop
import tempfile, shutil
import wave
import contextlib
from moviepy.audio.fx.all import audio_loop

class SubtitleBlock(tk.Label):
    highlight_color = "#f08080"

    def __init__(self, master, subtitle_json, manager, **kwargs):
        self.index: int = subtitle_json['index']
        self.start: float = subtitle_json['start']
        self.end: float = subtitle_json['end']
        self.text: str = subtitle_json['text']
        self.row: int = subtitle_json['row']
        self.col: int = subtitle_json['col']
        self.empty: bool = subtitle_json['empty']
        self.content: str = subtitle_json['content']
        self.num: int = subtitle_json['num']
        self.highlight: bool = subtitle_json['highlight']
        self.manager = manager

        if self.highlight:
            super().__init__(master, text=self.content, bg=SubtitleBlock.highlight_color, anchor='w', **kwargs)
        else:
            super().__init__(master, text=self.content, bg='white', anchor='w', **kwargs)

        self.bind("<Button-1>", self.on_click)
        # self.bind("<Return>", self.on_enter_key)
        # self.bind("<BackSpace>", self.on_backspace_key)
        # self.bind("<Up>", self.on_up_key)
        # self.bind("<Down>", self.on_down_key)
        # self.bind("<Left>", self.on_left_key)
        # self.bind("<Right>", self.on_right_key)
        # self.bind("<KeyPress-a>", self.on_a_key)
        # self.bind("<KeyPress-d>", self.on_d_key)
        # self.bind("<KeyPress-h>", self.on_h_key)
        self.bind("<Key>", self.on_key_press) # 한영키 해결 위해 키 입력 통합 (안되는데?)

    def on_click(self, event):
        """block 클릭 시 해당 인덱스를 선택 상태로 변경"""
        prev_block = self.manager.selected_SubtitleBlock

        
        if prev_block is not None: # 기존에 선택된 게 있다면
            if prev_block.highlight: # 그게 하이라이트라면
                prev_block.config(relief=tk.FLAT, bg=SubtitleBlock.highlight_color)
            else:
                prev_block.config(relief=tk.FLAT, bg='white')

        if prev_block == self:
            self.manager.selected_SubtitleBlock = None
            return

        # 선택된 블록 변경
        self.config(relief=tk.SUNKEN, bg="lightblue")
        self.focus_set()
        self.manager.selected_SubtitleBlock = self

        self.after(100, lambda: self.manager.scroll_x_to_widget(self.master.master, self))

    def on_key_press(self, event):
        keysym = event.keysym.lower()
  
        if keysym == 'return':
            self.on_enter_key(event)
        elif keysym == 'backspace':
            self.on_backspace_key(event)
        elif keysym == 'left':
            self.on_left_key(event)
        elif keysym == 'right':
            self.on_right_key(event)
        elif keysym == 'up':
            self.on_up_key(event)
        elif keysym == 'down':
            self.on_down_key(event)
        elif keysym == 'a':
            self.on_a_key(event)
        elif keysym == 'd':
            self.on_d_key(event)
        elif keysym == 'h':
            self.on_h_key(event)

    def on_enter_key(self, event):
        """엔터 키: 선택한 레이블 아래에 새 레이블 삽입"""
        cur_block = self.manager.selected_SubtitleBlock
        cur_index = cur_block.index
        cur_row = cur_block.row
        cur_col = cur_block.col
        nxt_row = cur_row + 1
        nxt_col = cur_col
        nxt_index = cur_index + 1
        
        # 빈 json 데이터 생성
        empty_json = {
            "index": nxt_index,
            "start": None,
            "end": None,
            "text": None,
            "row": nxt_row,
            "col": nxt_col,
            "empty": True,
            "content": "                      ",
            "num": -1,
            "highlight": None
        }

        # 새 레이블 생성
        empty_SubtitleBlock = SubtitleBlock(master=self.master, subtitle_json=empty_json, manager=self.manager)

        # 리스트에 삽입
        self.manager.SubtitleBlock_list.insert(nxt_index, empty_SubtitleBlock)

        # 나머지 블록 정보 갱신
        for index, block in enumerate(self.manager.SubtitleBlock_list): # 인덱스 갱신
            block.index = index

        new_index = empty_SubtitleBlock.index
        new_row = empty_SubtitleBlock.row
        new_col = empty_SubtitleBlock.col
        for block in self.manager.SubtitleBlock_list: # row 갱신
            if block.index <= new_index: 
               continue
            elif new_col == block.col and new_row <= block.row:
                block.row += 1


        # 자막 블록들 다시 그리기
        self.manager.draw_SubtitleBlocks()
        
        # 생성한 블록 클릭
        self.after(10, lambda: empty_SubtitleBlock.event_generate("<Button-1>"))

        # 자동 저장
        self.manager.auto_save()

    def on_backspace_key(self, event):
        """Backspace 키: 선택한 레이블 삭제"""
        cur_block = self.manager.selected_SubtitleBlock
        cur_index = cur_block.index
        cur_row = cur_block.row
        cur_col = cur_block.col
        cur_empty = cur_block.empty
        prev_block = self.manager.SubtitleBlock_list[cur_index-1]

        # 빈 블록이라면 제거
        if cur_empty:
            self.manager.SubtitleBlock_list.pop(cur_index)
            cur_block.destroy()
            self.manager.selected_SubtitleBlock = None

            # 나머지 블록 정보 갱신
            for index, block in enumerate(self.manager.SubtitleBlock_list): # 인덱스 갱신
                block.index = index

            for block in self.manager.SubtitleBlock_list: # row 갱신
                if block.index < cur_index: 
                    continue
                elif block.col == cur_col and cur_row < block.row:
                    block.row -= 1


            # 자막 블록들 다시 그리기
            self.manager.draw_SubtitleBlocks()
            
            # 이전 블록 클릭
            self.after(10, lambda: prev_block.event_generate("<Button-1>"))

            # 자동 저장
            self.manager.auto_save()

    def on_up_key(self, event):
        """위쪽 화살표 키: 선택한 레이블 위로 이동"""
        cur_block = self.manager.selected_SubtitleBlock
        cur_index = cur_block.index
        nxt_index = cur_index - 1
        if nxt_index < 0:
            return
        nxt_block = self.manager.SubtitleBlock_list[nxt_index]
        nxt_block.event_generate("<Button-1>")

    def on_down_key(self, event):
        """아래쪽 화살표 키: 선택한 레이블 아래로 이동"""
        cur_block = self.manager.selected_SubtitleBlock
        cur_index = cur_block.index
        nxt_index = cur_index + 1
        if nxt_index >= len(self.manager.SubtitleBlock_list):
            return
        nxt_block = self.manager.SubtitleBlock_list[nxt_index]
        nxt_block.event_generate("<Button-1>")

    def on_left_key(self, event):
        """왼쪽 화살표 키: 선택한 레이블 왼쪽으로 이동"""
        cur_block = self.manager.selected_SubtitleBlock
        cur_col = cur_block.col
        cur_row = cur_block.row

        if cur_col == 0:
            return
        
        for block in self.manager.SubtitleBlock_list:
            if block.col == cur_col-1:
                nxt_block = block
                if block.row == cur_row:
                    break

        nxt_block.event_generate("<Button-1>")

    def on_right_key(self, event):
        """오른쪽 화살표 키: 선택한 레이블 오른쪽으로 이동"""
        cur_block = self.manager.selected_SubtitleBlock
        cur_col = cur_block.col
        cur_row = cur_block.row

        if cur_col == self.manager.SubtitleBlock_list[-1].col:
            return
        
        for block in self.manager.SubtitleBlock_list:
            if block.col == cur_col+1:
                nxt_block = block
                if block.row == cur_row:
                    break
                
        nxt_block.event_generate("<Button-1>")

    def on_a_key(self, event):
        cur_block = self.manager.selected_SubtitleBlock
        cur_col = cur_block.col

        if cur_col == 0:
            return

        for index, block in enumerate(self.manager.SubtitleBlock_list):
            prev_block = self.manager.SubtitleBlock_list[index-1]
       
            if block.col == cur_col: 
                block.row = prev_block.row + 1
            if cur_col <= block.col:
                block.col -= 1
                
            
        # 자막 블록들 다시 그리기
        self.manager.draw_SubtitleBlocks()

        # 자동 저장
        self.manager.auto_save()

    def on_d_key(self, event):
        cur_block = self.manager.selected_SubtitleBlock
        cur_index = cur_block.index
        cur_row = cur_block.row
        cur_col = cur_block.col

        for block in self.manager.SubtitleBlock_list[cur_index+1:]:
            if block.col == cur_col: 
                block.row -= cur_row+1
            block.col += 1
            
        # 자막 블록들 다시 그리기
        self.manager.draw_SubtitleBlocks()

        # 다음 블록 클릭
        nxt_block = self.manager.SubtitleBlock_list[cur_index+1]
        self.after(10, lambda: nxt_block.event_generate("<Button-1>"))

        # 자동 저장
        self.manager.auto_save()

    def on_h_key(self, event):
        if self.highlight:
            self.config(relief=tk.SUNKEN, bg="white")
            self.highlight = False
        else:     
            self.config(relief=tk.SUNKEN, bg=SubtitleBlock.highlight_color)
            self.highlight = True
        # 자동 저장   
        self.manager.auto_save()


class SubtitleManager():
    def __init__(self, txt_file_path, srt_file_path, json_file_path):
        self.SubtitleBlock_list: list[SubtitleBlock] = []
        self.selected_SubtitleBlock: SubtitleBlock = None
        self.txt_file_path = txt_file_path
        self.srt_file_path = srt_file_path
        self.json_file_path = json_file_path

    def read_txt(self):
        with open(self.txt_file_path, 'r', encoding='utf-8') as txt_file:
            txts = [line.strip() for line in txt_file if line.strip()]
        return txts

    def read_srt(self):
        subtitles:list[tuple] = file_to_subtitles(self.srt_file_path)
        return subtitles
    
    def read_json(self):
        with open(self.json_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
        
    def delete_json(self): # json 파일을 지운다.
        if os.path.exists(self.json_file_path):
            os.remove(self.json_file_path)
            print(f"{self.json_file_path} 파일을 삭제했습니다.")
        else:
            print(f"{self.json_file_path} 파일이 존재하지 않습니다.")

    def srt_to_json(self):  # subtitles.srt파일을 subtitles.json으로 변환한다.
        result = []
        subtitles = self.read_srt()

        for subtitle in enumerate(subtitles):
            index, ((start, end), text) = subtitle
            subtitle_data = {
                "index": index,
                "start": start,
                "end": end,
                "text": text,
                "row": index, 
                "col": 0,  
                "empty": False,
                "content": f"{index}. {start:.2f} ~ {end:.2f}: {text}",
                "num": index,
                "highlight": False
            }
            result.append(subtitle_data)

        with open(self.json_file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        print("srt -> json 생성이 완료되었습니다.")

    def txt_and_srt_to_json(self): # subtitles.txt파일의 텍스트와 subtitles.srt의 타임라인을 json으로 만든다.
        # 1. txt 파일의 텍스트를 줄바꿈 기준으로 스플릿
        # 2. srt 파일의 타임라인을 파싱
        # 3. 각 데이터를 json으로 생성
        # 이 함수가 있으면 srt_to_json함수는 필요가 없다.
        result = []
        txt = self.read_txt()
        srt = self.read_srt()

        for subtitle in enumerate(srt):
            index, ((start, end), _) = subtitle
            subtitle_data = {
                "index": index,
                "start": start,
                "end": end,
                "text": txt[index],
                "row": index, 
                "col": 0,  
                "empty": False,
                "content": f"{index}. {start:.2f} ~ {end:.2f}: {txt[index]}",
                "num": index,
                "highlight": False
            }
            result.append(subtitle_data)

        with open(self.json_file_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=4)

        print("txt + srt -> json 생성이 완료되었습니다.")

    def json_to_SubtitleBlock_list(self, canvas): # subtitles.json 파일을 SubtitleBlock 리스트로 변환한다.
        json_data = self.read_json()
        self.SubtitleBlock_list = [SubtitleBlock(master=canvas, subtitle_json=subtitle, manager=self) for subtitle in json_data]
        return self.SubtitleBlock_list
    
    def draw_SubtitleBlocks(self): # subtitles.json 파일을 캔버스에 그린다.
        if self.SubtitleBlock_list: # 기존 요소 제거
            frame = self.SubtitleBlock_list[0].master
            for block in frame.winfo_children():
                block.grid_forget()
        for block in self.SubtitleBlock_list: 
            block.grid(row=block.row, column=block.col, padx=5, sticky='w')
            canvas = block.master.master
            canvas.after(100, lambda: canvas.configure(scrollregion=canvas.bbox("all"))) # 지연예약을 걸 뿐 100ms를 기다렸다가 실행되는 건 아님.

    def SubtitleBlock_list_to_json(self):
        data = []
        for block in self.SubtitleBlock_list:
            data.append({
                'index': block.index,
                'start': block.start,
                'end': block.end,
                'text': block.text,
                'row': block.row,
                'col': block.col,
                'empty': block.empty,
                'content': block.content,
                "num": block.num,
                "highlight": block.highlight
            })

        with open(self.json_file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    
    def auto_save(self):
        self.SubtitleBlock_list_to_json()
    
    def scroll_x_to_widget(self, canvas, block): # 선택된 블록이 화면을 벗어나면 스크롤한다.
        canvas.update_idletasks()
        canvas_left_frac, canvas_right_frac = canvas.xview()
        canvas_width = canvas.bbox("all")[2] - canvas.bbox("all")[0]
        visible_left_x = canvas_left_frac * canvas_width
        visible_right_x = canvas_right_frac * canvas_width
        visible_width = visible_right_x - visible_left_x

        # block_width = block.winfo_width()
        block_left_x = block.winfo_x()
        # block_right_x = block.winfo_x() + block_width
        max_block_right_x_in_col = -1
        for b in self.SubtitleBlock_list:
            b_right_x = b.winfo_x() + b.winfo_width()
            if b.col == block.col and max_block_right_x_in_col < b_right_x:
                max_block_right_x_in_col = b_right_x

        # 위젯이 왼쪽에 가려진 경우
        if block_left_x <= visible_left_x:
            scroll_to = block_left_x / canvas_width
            canvas.xview_moveto(scroll_to)
        # 위젯이 오른쪽에 가려진 경우
        elif visible_right_x <= max_block_right_x_in_col:
            scroll_to = (max_block_right_x_in_col - visible_width) / canvas_width
            canvas.xview_moveto(scroll_to)

class TkinterLogger(ProgressBarLogger):


    def __init__(self, progress_callback, total):
        super().__init__()
        self.total = total
        self.progress_callback = progress_callback

    def bars_callback(self, bar, attr, value, old_value=None):
        if bar == 't':
            percent = round(float(value) / self.total * 100, 1)
            self.progress_callback(percent)
            print(percent)

class ShortsGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("영상 제작 프로그램")
        screen_width =  root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        root_width = 1000
        root_height = 1080
        x = (screen_width // 2) - (root_width // 2)
        y = (screen_height // 2) - (root_height // 2) - 400
        self.root.geometry(f"{root_width}x{root_height}+{x}+{y}")
        self.root.minsize(600, 600)  # 최소 크기 설정
        self.work_dir = None
        # self.bg_color = '#e6f2ff' # 하늘색
        # self.bg_color = '#ffccb6'
        # self.bg_color = '#c6dbda'
        self.bg_color = '#bbd4dd'
        icon = Image.open('/Users/sangwoo-park/ssul-shorts-project/달녹/채널 로고.png')
        root.iconphoto(False, ImageTk.PhotoImage(icon)) 
        self.subtitle_manager = None # 자막 관리 매니저. 폴더 선택할 때 생성됨.

        # root.after(100, self.subtitle_manager.draw_SubtitleBlocks())  # 100ms 후에 실행

        # 메인 프레임
        main_frame = tk.Frame(root, bg=self.bg_color, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 상단: 프로그램 이름
        self.greeting_label = tk.Label(main_frame, bg=self.bg_color, text="영상 자동 생성기", font=("Helvetica", 24, "bold"))
        self.greeting_label.pack(pady=(0, 10))

        # 설명 Frame
        desc_frame = tk.Frame(main_frame, bg=self.bg_color, padx=10, pady=10, bd=2, relief=tk.GROOVE)
        desc_frame.pack(fill=tk.X, pady=(0, 20))

        self.program_description = tk.Label(desc_frame, bg=self.bg_color, text=(
            "1. 작업 폴더 선택\n"
            "   - 작업 폴더 내에는 반드시 `tts.wav`와 `subtitles.srt` 파일, images 폴더가 존재해야 합니다.\n"
            "   - subtitles.srt의 마지막 2줄은 빈 줄이어야 합니다.\n"
            "2. 영상 제목 입력\n"
            "3. 영상 제작 시작\n"
            "=> 작업 폴더 내 result 폴더에 결과물이 저장됩니다."
        ), font=("Helvetica", 14), justify="left", anchor="w")
        self.program_description.pack(fill=tk.X)

        # 작업 폴더 선택 Frame
        folder_frame = tk.Frame(main_frame, bg=self.bg_color, pady=10)
        folder_frame.pack(fill=tk.X)

        # 작업 폴더 선택 레이블
        folder_title_label = tk.Label(folder_frame, bg=self.bg_color, text="작업 폴더 선택", font=("Helvetica", 14, "bold"), anchor="w")
        folder_title_label.pack(fill=tk.X)

        # 작업 폴더 경로 + 버튼을 담을 하위 Frame
        work_dir_path_frame = tk.Frame(folder_frame, bg=self.bg_color)
        work_dir_path_frame.pack(fill=tk.X, pady=(5, 0))

        # 작업 폴더 경로 레이블
        self.folder_label = tk.Label(work_dir_path_frame, bg=self.bg_color, text="(폴더를 선택하면 경로가 나타납니다)", anchor="w", wraplength=700)
        self.folder_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 작업 폴더 선택 버튼 (조그맣게)
        self.select_button = tk.Button(work_dir_path_frame, bg=self.bg_color, text="폴더 선택", width=10, highlightbackground=self.bg_color, command=self.select_work_dir)
        self.select_button.pack(side=tk.RIGHT, padx=5)

        # tts 생성 Frame
        generate_tts_frame = tk.Frame(main_frame, bg=self.bg_color, pady=10)
        generate_tts_frame.pack(fill=tk.X)

        # tts 생성 레이블
        generate_tts_label = tk.Label(generate_tts_frame, bg=self.bg_color, text="tts 생성", font=("Helvetica", 14, "bold"), anchor="w")
        generate_tts_label.pack(fill=tk.X)

        # tts 생성 버튼
        self.generate_tts_button = tk.Button(generate_tts_frame, bg=self.bg_color, text="tts 생성", width=10, highlightbackground=self.bg_color, command=self.generate_tts)
        self.generate_tts_button.pack(side=tk.LEFT, padx=5)

        # 영상 제목 입력 Frame
        title_frame = tk.Frame(main_frame, bg=self.bg_color, pady=10)
        title_frame.pack(fill=tk.X)

        # 영상 제목 입력 레이블
        video_title_label = tk.Label(title_frame, bg=self.bg_color, text="영상 제목 입력", font=("Helvetica", 14, "bold"), anchor="w")
        video_title_label.pack(fill=tk.X)

        # 영상 제목 입력 Entry
        self.title_entry = tk.Entry(title_frame, justify='left', highlightbackground=self.bg_color)
        self.title_entry.pack(fill=tk.X, pady=(5, 0))

        # 자막 설정 Frame
        self.subtitles_frame = tk.Frame(main_frame, bg=self.bg_color, pady=10)
        self.subtitles_frame.pack(fill=tk.BOTH, expand=True)
        self.subtitles_frame.columnconfigure(0, weight=1)
        self.subtitles_frame.columnconfigure(1, weight=0)
        self.subtitles_frame.rowconfigure(0, weight=0)
        self.subtitles_frame.rowconfigure(1, weight=1)
        self.subtitles_frame.rowconfigure(2, weight=0)

        # 자막 설정 레이블
        self.subtitles_setting_label = tk.Label(self.subtitles_frame, bg=self.bg_color, text="자막 설정", font=("Helvetica", 14, "bold"), anchor="w")
        self.subtitles_setting_label.grid(row=0, column=0, sticky='w')

        # 자막 설정 캔버스
        self.subtitles_canvas = tk.Canvas(self.subtitles_frame, bg='white', bd=0, highlightthickness=0)
        self.subtitles_canvas.grid(row=1, column=0, sticky='nsew')

        # 자막 설정 캔버스 y스크롤바
        self.subtitles_yScrollbar = ttk.Scrollbar(self.subtitles_frame, orient='vertical', command=self.subtitles_canvas.yview)
        self.subtitles_yScrollbar.grid(row=1, column=1, sticky='ns')
        self.subtitles_canvas.configure(yscrollcommand=self.subtitles_yScrollbar.set)
        self.subtitles_canvas.bind_all('<MouseWheel>', lambda e: self.subtitles_canvas.yview_scroll(int(e.delta*(-1)/2), "units"))

        # 자막 설정 캔버스 x스크롤바
        self.subtitles_xScrollbar = ttk.Scrollbar(self.subtitles_frame, orient='horizontal', command=self.subtitles_canvas.xview)
        self.subtitles_xScrollbar.grid(row=2, column=0, stick='we')
        self.subtitles_canvas.configure(xscrollcommand=self.subtitles_xScrollbar.set)

        # 자막 설정 main Frame
        self.subtitles_canvas_main_frame = tk.Frame(self.subtitles_canvas, bg='white')
        self.subtitles_canvas.create_window((0, 0), window=self.subtitles_canvas_main_frame, anchor='nw')

        # json reset button
        self.reset_json_button = tk.Button(main_frame, text="초기화", font=("Helvetica", 14), command=self.reset_json, highlightbackground=self.bg_color)
        self.reset_json_button.pack()

        # 하단 Spacer
        spacer = tk.Frame(main_frame, bg=self.bg_color)
        spacer.pack(fill=tk.BOTH, expand=True)

        # 영상 제작 시작 + 체크박스를 묶을 Frame
        start_frame = tk.Frame(main_frame, bg=self.bg_color)
        start_frame.pack(pady=20)

        # 영상 제작 시작 버튼
        self.start_button = tk.Button(start_frame, text="영상 제작 시작", font=("Helvetica", 14), command=self.start_creation, highlightbackground=self.bg_color, state=tk.DISABLED)
        self.start_button.pack(side=tk.LEFT, padx=(0, 10))

        # 일부만 렌더링할지 여부 체크박스
        self.partial_render_var = tk.BooleanVar()
        self.partial_render_check = tk.Checkbutton(
            start_frame,
            text="일부(5초)만 렌더링",
            variable=self.partial_render_var,
            bg=self.bg_color,
            font=("Helvetica", 12)
        )
        self.partial_render_check.pack(side=tk.LEFT)

        # 프로그램 종료
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def select_work_dir(self):
        folder = filedialog.askdirectory(title="작업 폴더 선택")
        if folder:
            self.work_dir = folder
            self.folder_label.config(text=f"선택된 폴더: {folder}")
            self.start_button.config(state=tk.NORMAL)  # 폴더 선택하면 버튼 활성화

            txt_file_path = os.path.join(self.work_dir, "subtitles.txt")
            srt_file_path = os.path.join(self.work_dir, "subtitles.srt")
            json_file_path = os.path.join(self.work_dir, "subtitles.json")
            self.subtitle_manager = SubtitleManager(txt_file_path, srt_file_path, json_file_path)

            if not os.path.exists(json_file_path):
                self.subtitle_manager.srt_to_json()
                # self.subtitle_manager.txt_and_srt_to_json()
            self.subtitle_manager.json_to_SubtitleBlock_list(canvas=self.subtitles_canvas_main_frame)
            self.subtitle_manager.draw_SubtitleBlocks()

    def generate_tts(self):
        auto_vrew.main(os.path.join(self.work_dir, "subtitles.txt"))
        print("tts 생성 완료.")

    def show_loading_popup(self):
        # 팝업 창을 띄워서 제작 중 메시지를 표시
        self.loading_popup = tk.Toplevel(self.root)
        self.loading_popup.title("영상 제작 중")
        self.loading_popup.geometry("300x150")
        self.loading_popup.resizable(False, False)
        
        # 팝업 내용 (제작 중 표시)
        self.progress_bar = ttk.Progressbar(self.loading_popup, orient='horizontal', length=300, mode='determinate', maximum=100)
        self.progress_bar.pack(pady=(20, 0))

        self.percent_label = tk.Label(self.loading_popup, text="", font=("Helvetica", 14), padx=20, pady=0)
        self.percent_label.pack(fill=tk.BOTH, expand=True)

        self.loading_label = tk.Label(self.loading_popup, text="영상 제작 중입니다...\n잠시만 기다려주세요.", font=("Helvetica", 14), padx=20, pady=20)
        self.loading_label.pack(fill=tk.BOTH, expand=True)

        # 부모(root) 기준으로 중앙에 배치
        self.root.update_idletasks()  # geometry 정보를 최신화
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()

        popup_width = 300
        popup_height = 150
        x = root_x + (root_width // 2) - (popup_width // 2)
        y = root_y + (root_height // 2) - (popup_height // 2)

        self.loading_popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

    def close_loading_popup(self):
        if hasattr(self, 'loading_popup') and self.loading_popup.winfo_exists():
            self.loading_popup.destroy()
            self.loading_popup = None
    
    def reset_json(self): # json 파일을 txt, srt파일의 상태인 초기 상태로 재생성한다.
        if self.subtitle_manager:
            answer = messagebox.askyesno("확인", "정말 초기화하시겠습니까?")
            if answer:
                self.subtitle_manager.delete_json()
                self.subtitle_manager.txt_and_srt_to_json()
                self.subtitle_manager.json_to_SubtitleBlock_list(canvas=self.subtitles_canvas_main_frame)
                self.subtitle_manager.draw_SubtitleBlocks()
                print("초기화 완료.")
        else:
            print("초기화할 수 없습니다.")

    def load_files(self):
        paths = {
            "tts": os.path.join(self.work_dir, "tts.wav"),
            "background_music": '/Users/sangwoo-park/수학 공부법 사업/02-Brahms-Hungarian_Dances-Dorati1957-65-Track1.mp3',
            "subtitles": os.path.join(self.work_dir, "subtitles.srt"),
            "images_folder": os.path.join(self.work_dir, 'images')
        }
        return paths
    
    def update_progress(self, percent):
        percent = min(100, percent)
        self.progress_bar['value'] = percent

        self.percent_label.config(text=f"{percent}%", font=("Helvetica", 14))
        self.percent_label.pack(fill=tk.BOTH, expand=True,)

        self.loading_label.config(text="영상 제작 중입니다...\n잠시만 기다려주세요.")
        self.loading_label.pack(fill=tk.BOTH, expand=True)

        root.update_idletasks()

    def start_creation(self):
        if not self.work_dir:
            messagebox.showerror("오류", "작업 폴더를 먼저 선택하세요.")
            return
        self.show_loading_popup()
        self.root.update() 

        files = self.load_files()
        threading.Thread(target=self.create_video, args=(files,)).start() # 다른 스레드에서 영상 제작 <-- 진행률 로그를 위한 것 
        # self.create_video(files)
        
    def create_video(self, files):
        
        try:
            title = self.title_entry.get() 
            if title == "":
                title = "제목없음"

            with contextlib.closing(wave.open(files['tts'], 'r')) as f:
                frames = f.getnframes()
                rate = f.getframerate()
                total_duration = int(frames / float(rate)) + 1
            
            # 1. 레이아웃 클립 생성
            layout_clip = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=total_duration)

            # 2. 자막 클립 리스트 생성
            subtitle_clips = []

            prev_col = -1
            for subtitle_label in reversed(self.subtitle_manager.SubtitleBlock_list):
                if subtitle_label.empty:
                    continue

                start = subtitle_label.start
                end = subtitle_label.end
                col = subtitle_label.col
                text = str(subtitle_label.text)
                row = subtitle_label.row
                col = subtitle_label.col

                txt_clip = (
                    TextClip(
                        text, 
                        fontsize=50, 
                        color='white', 
                        font="/Users/sangwoo-park/Library/Fonts/BMDOHYEON_otf.otf",       
                    )
                    .set_start(start)
                    .set_end(end)
                    .set_position(('center', 900))
                )


                subtitle_clips.append(txt_clip)
            # 3. 자료화면 클립 리스트 생성
            temp_dir = tempfile.mkdtemp() # 임시 디렉토리
            # 동적 crop 처리 함수
            def make_dynamic_crop(new_width, new_height, effect_code):
                def dynamic_crop(get_frame, t):
                    frame = get_frame(t)  # t초에서의 프레임 (numpy 배열)

                    # 기본 crop 범위 (전체)
                    x1, x2 = 0, new_width
                    y1, y2 = 0, new_height
                    
                    # crop 좌표 계산
                    if effect_code == 'l':  # 왼쪽으로 이동
                        x1 = int(new_width*0.1 + t*-20)   # 초당 -20px 왼쪽 이동
                        x2 = int(x1 + new_width*0.9)      # 가로 크기 유지
                        y1 = int(new_height*0.05)
                        y2 = int(new_height*0.95)
                    elif effect_code == 'r':  # 오른쪽으로 이동
                        x1 = int(0 + t*20)                # 초당 20px 오른쪽 이동
                        x2 = int(x1 + new_width*0.9)      # 가로 크기 유지
                        y1 = int(new_height*0.05)
                        y2 = int(new_height*0.95)
                    elif effect_code == 'u':  # 위로 이동
                        x1 = int(new_width*0.05)
                        x2 = int(new_width*0.95)
                        y1 = int(new_height*0.1 + t*-20)   # 초당 -20px 위쪽 이동
                        y2 = int(y1 + new_height*0.9)      # 세로 크기 유지
                    elif effect_code == 'd':  # 아래로 이동
                        x1 = int(new_width*0.05)
                        x2 = int(new_width*0.95)
                        y1 = int(0 + t*20)                 # 초당 20px 아래쪽 이동
                        y2 = int(y1 + new_height*0.9)      # 세로 크기 유지
                    elif effect_code == 'i':  # 확대 (줌인)
                        center_x = new_width // 2
                        center_y = new_height // 2
                        zoom_factor = 1 + t * 0.05  # 초당 0.1배 확대
                        crop_width = new_width / zoom_factor
                        crop_height = new_height / zoom_factor

                        x1 = max(0, center_x - crop_width / 2)
                        x2 = min(new_width, x1 + crop_width)
                        y1 = max(0, center_y - crop_height / 2)
                        y2 = min(new_height, y1 + crop_height)
                    elif effect_code == 'o':  # 축소 (줌아웃)
                        center_x = new_width // 2
                        center_y = new_height // 2
                        zoom_factor = max(1, 1.3 + t * -0.05)  # 초당 0.07배 축소
                        crop_width = new_width / zoom_factor
                        crop_height = new_height / zoom_factor

                        x1 = max(0, center_x - crop_width / 2)
                        x2 = min(new_width, x1 + crop_width)
                        y1 = max(0, center_y - crop_height / 2)
                        y2 = min(new_height, y1 + crop_height)

                    elif effect_code == 'n':  # 효과 없음
                        pass
                    else:
                        raise ValueError(f"❌ 알 수 없는 effect_code: {effect_code}")
                    
                    cropped = frame[int(y1):int(y2), int(x1):int(x2)]
                        
                    # crop된 부분을 원래 캔버스 크기로 resize
                    pil_img = Image.fromarray(cropped)
                    resized = pil_img.resize((new_width, new_height), resample=Image.LANCZOS)

                    return np.array(resized)
                return dynamic_crop

            image_clips = []
            gif_clips = []
            video_clips = []
            images_dir = os.path.join(self.work_dir, 'images')
            image_file_names = sorted([f for f in os.listdir(images_dir) if not f.startswith('.') and os.path.isfile(os.path.join(images_dir, f))])
            
            for img_name in image_file_names:
                img_num, ext = os.path.splitext(img_name) # 마지막 글자 제외
                img_num = img_num[:-1]
                img_path = os.path.join(images_dir, img_name)
                effect_code = os.path.splitext(img_name)[0][-1]

                # start, end, row, ypos, duration 정의
                if img_num.isdigit(): # 숫자만
                    img_num = int(img_num)
                    for block in self.subtitle_manager.SubtitleBlock_list:
                        if block.num == img_num:
                            subtitle_label = block
                            break   
                    start = subtitle_label.start
                    end = subtitle_label.end
                    ypos = 150
                    duration = end - start
                elif re.match(r'^\d+-\d+$', img_num): # 숫자-숫자
                    img_num1, img_num2 = map(int, img_num.split('-'))
                    for block in self.subtitle_manager.SubtitleBlock_list:
                        if block.num == img_num1:
                            subtitle_label1 = block
                            break
                    for block in self.subtitle_manager.SubtitleBlock_list:
                        if block.num == img_num2:
                            subtitle_label2 = block
                            break
                    start = subtitle_label1.start
                    end = subtitle_label2.end
                    row = subtitle_label2.row
                    ypos = 150
                    duration = end - start
                else:
                    print("자료화면 이름이 잘못되었습니다.")

                # 이미지 리사이징
                img = Image.open(img_path)
                width, height = img.size
                new_height = 650
                aspect_ratio = width / height
                new_width = int(new_height * aspect_ratio) 

                if ext == '.gif':
                        # 모든 프레임 리사이즈
                    frames = []
                    for frame in ImageSequence.Iterator(img):
                        resized_frame = frame.resize((new_width, new_height)).convert("RGB")
                        frames.append(resized_frame)
                    resized_gif_path = os.path.join(temp_dir, "resized.gif")

                    # 첫 프레임에 나머지 프레임들 붙여서 저장
                    frames[0].save(
                        resized_gif_path,
                        save_all=True,
                        append_images=frames[1:],
                        duration=img.info.get('duration', 100),
                        loop=img.info.get('loop', 0),
                        disposal=2,
                    )

                    gif_clip = VideoFileClip(resized_gif_path).loop(duration=duration)
                    gif_clip = gif_clip.set_duration(duration).set_start(start).set_position(('center', ypos))
                    gif_clips.append(gif_clip)
                # elif ext == '.mp4':
                #     video_clip = VideoFileClip()
                else:
                    resized_img = img.resize((new_width, new_height)).convert("RGB")
                    resized_img_path = os.path.join(temp_dir, "resized.jpg")
                    resized_img.save(resized_img_path)
                    
                    image_clip = ImageClip(resized_img_path).set_duration(duration).set_start(start).set_position(('center', ypos))
                    image_clip = image_clip.fl(make_dynamic_crop(new_width, new_height, effect_code))
                    image_clips.append(image_clip)  
            
            # 4. 오디오 클립 리스트 생성
            
            tts_clip = AudioFileClip(files['tts'])
            background_music_clip = audio_loop(AudioFileClip(files['background_music']), duration=total_duration)
            all_audio_clip = CompositeAudioClip([tts_clip] + [background_music_clip])   

            # 최종 클립: 레이아웃 클립 + 제목 클립 + 자막 클립 + 이미지 클립 + 오디오 클립
            final_clip = CompositeVideoClip([layout_clip] + subtitle_clips + image_clips + gif_clips).set_audio(all_audio_clip)
            if self.partial_render_var.get(): # 테스트용으로 일부만 렌더링
                final_clip = final_clip.subclip(0, 5)

            # 클립을 비디오로 생성
            result_folder = Path(self.work_dir).joinpath("result")
            result_folder.mkdir(parents=True, exist_ok=True)
            output_path = str(result_folder.joinpath(f"{title}.mov"))
            logger = TkinterLogger(self.update_progress, final_clip.duration*30)
            final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac", fps=30, logger=logger)
            self.root.after(0, self.on_video_complete)
            shutil.rmtree(temp_dir) # 임시 디렉토리 삭제
        except Exception as e:
              self.close_loading_popup()
              error_message = f"영상 제작 중 문제가 발생했습니다: {e}\n\n" \
                        f"오류 위치:\n{traceback.format_exc()}"
              messagebox.showerror("오류", error_message)
        
    def on_video_complete(self):
        self.close_loading_popup()
        messagebox.showinfo("완료", f"영상 제작이 완료되었습니다!")

    def on_close(self):
        if self.subtitle_manager:
            if self.subtitle_manager.SubtitleBlock_list:
                self.subtitle_manager.SubtitleBlock_list_to_json()
        self.root.destroy()
        print("종료")

if __name__ == "__main__":
    root = tk.Tk()
    app = ShortsGeneratorApp(root)
    root.mainloop()

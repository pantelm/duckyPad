import os
import hid
import time
import shutil
import filecmp

def ensure_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)

def get_file_content(file_path):
    this_file = open(file_path, encoding='utf-8')
    content = this_file.read()
    this_file.close()
    return content

def get_duckypad_path():
	for device_dict in hid.enumerate():
	    if device_dict['vendor_id'] == 0x0483 and \
	    device_dict['product_id'] == 0xd11c and \
	    device_dict['usage'] == 58:
	    	return device_dict['path']
	return None

class my_file_obj(object):
	def __init__(self, name, ftype, content):
		super(my_file_obj, self).__init__()
		self.name = name
		self.content = content
		self.type = ftype
	def __str__(self):
		ret = ""
		ret += str('...............') + '\n'
		ret += "name:\t" + str(self.name) + '\n'
		ret += "type:\t" + str(self.type) + '\n'
		ret += "content:\t" + str(self.content) + '\n'
		ret += str('...............') + '\n'
		return ret

PC_TO_DUCKYPAD_HID_BUF_SIZE = 64
DUCKYPAD_TO_PC_HID_BUF_SIZE = 64

HID_RESPONSE_OK = 0
HID_RESPONSE_ERROR = 1
HID_RESPONSE_BUSY = 2
HID_RESPONSE_EOF = 3

HID_COMMAND_LIST_FILES = 10
HID_COMMAND_READ_FILE = 11
HID_COMMAND_OP_RESUME = 12
HID_COMMAND_OP_ABORT = 13
HID_COMMAND_OPEN_FILE_FOR_WRITING = 14
HID_COMMAND_WRITE_FILE = 15
HID_COMMAND_CLOSE_FILE = 16
HID_COMMAND_DELETE_FILE = 17
HID_COMMAND_CREATE_DIR = 18
HID_COMMAND_DELETE_DIR = 19
HID_COMMAND_SW_RESET = 20

h = hid.device()

def duckypad_hid_init():
	duckypad_path = get_duckypad_path()
	if duckypad_path is None:
		raise OSError('duckyPad Not Found!')
	h.open_path(duckypad_path)

def duckypad_hid_close():
	h.close()


def duckypad_list_files(root_dir = None):
	ret = []
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_LIST_FILES	# Command type

	if root_dir is not None:
		for x in range(0, len(root_dir)):
			pc_to_duckypad_buf[3+x] = ord(root_dir[x])

	h.write(pc_to_duckypad_buf)
	while 1:
		# time.sleep(HID_WAIT_TIME)
		result = h.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
		if len(result) == 0 or result[2] == HID_RESPONSE_EOF:
			break
		if result[2] == HID_RESPONSE_BUSY or result[2] == HID_RESPONSE_ERROR:
			raise OSError("HID read error or busy")
		# print(result)
		this_filename = ("".join([chr(x) for x in result[4:]]).strip('\0'), result[3])
		# print(this_filename)
		ret.append(this_filename)
		duckypad_hid_resume()
	return ret

def duckypad_hid_resume():
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_OP_RESUME	# Command type
	h.write(pc_to_duckypad_buf)

def duckypad_read_file(file_dir):
	ret = ''
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_READ_FILE	# Command type

	for x in range(0, len(file_dir)):
		pc_to_duckypad_buf[3+x] = ord(file_dir[x])

	h.write(pc_to_duckypad_buf)
	while 1:
		# time.sleep(HID_WAIT_TIME)
		result = h.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
		if result[2] == HID_RESPONSE_BUSY or result[2] == HID_RESPONSE_ERROR:
			raise OSError("HID read error or busy")
		# print(result)
		# print("".join([chr(x) for x in result]))
		ret += "".join([chr(x) for x in result[3:]]).strip('\0')
		if len(result) == 0 or result[2] == HID_RESPONSE_EOF:
			break
		duckypad_hid_resume()
	return ret

def dump_from_hid(save_path, string_var):
	file_struct_list = []
	# top level
	for item in duckypad_list_files():
		file_struct_list.append(my_file_obj(item[0], item[1], None))

	for item in file_struct_list:
		if item.type == 0:
			if not item.name.lower().startswith("dp_"):
				continue
			string_var.set("Loading " + str(item.name))
			item.content = duckypad_read_file(item.name)
		if item.type == 1:
			if 'keymap' in item.name:
				continue
			if 'profile' not in item.name.lower():
				continue
			files_in_this_dir = duckypad_list_files(item.name)
			lv2_list = []
			for fff in files_in_this_dir:
				string_var.set("Loading " + str(item.name + "/" + fff[0]))
				if fff[1] != 0:
					continue
				lv2_list.append(my_file_obj(fff[0], fff[1], duckypad_read_file(item.name + "/" + fff[0])))
			item.content = lv2_list

	try:
	    shutil.rmtree(save_path)
	    time.sleep(0.05)
	except FileNotFoundError:
	    pass
	ensure_dir(save_path)

	for item in file_struct_list:
		if item.type == 0 and item.content is not None:
			with open(os.path.join(save_path, item.name), 'w', encoding='utf-8') as this_file:
				this_file.write(item.content)

		if item.type == 1 and item.content is not None:
			this_folder_path = os.path.join(save_path, item.name)
			ensure_dir(this_folder_path)
			for subfile in item.content:
				if subfile.type == 0 and subfile.content is not None:
					with open(os.path.join(this_folder_path, subfile.name), 'w', encoding='utf-8') as this_file:
						this_file.write(subfile.content)


def duckypad_open_file_for_writing(file_dir):
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_OPEN_FILE_FOR_WRITING	# Command type

	for x in range(0, len(file_dir)):
		pc_to_duckypad_buf[3+x] = ord(file_dir[x])

	h.write(pc_to_duckypad_buf)

	result = h.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
	# print(result)

def duckypad_close_file():
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_CLOSE_FILE	# Command type

	h.write(pc_to_duckypad_buf)

	result = h.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
	# print(result)

def duckypad_write_file_one_line(content):
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_WRITE_FILE	# Command type

	if len(content) > 60:
		raise ValueError("content too long")

	for x in range(0, len(content)):
		if 0 <= ord(content[x]) <= 255:
			pc_to_duckypad_buf[3+x] = ord(content[x])
		else:
			pc_to_duckypad_buf[3+x] = ord("?")

	h.write(pc_to_duckypad_buf)

	result = h.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
	# print(result)

def duckypad_write_file(content):
	n=60
	line_list = [content[i:i+n] for i in range(0, len(content), n)]
	# print(line_list)
	for line in line_list:
		duckypad_write_file_one_line(line)

def duckypad_delete_file(file_name):
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_DELETE_FILE	# Command type

	for x in range(0, len(file_name)):
		pc_to_duckypad_buf[3+x] = ord(file_name[x])

	h.write(pc_to_duckypad_buf)

	result = h.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
	# print(result)

def duckypad_create_dir(dir_name):
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_CREATE_DIR	# Command type

	for x in range(0, len(dir_name)):
		pc_to_duckypad_buf[3+x] = ord(dir_name[x])

	h.write(pc_to_duckypad_buf)

	result = h.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
	# print(result)

def duckypad_delete_dir(dir_name):
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_DELETE_DIR	# Command type
	for x in range(0, len(dir_name)):
		pc_to_duckypad_buf[3+x] = ord(dir_name[x])
	h.write(pc_to_duckypad_buf)
	result = h.read(DUCKYPAD_TO_PC_HID_BUF_SIZE)
	# print(result)

def duckypad_hid_file_sync(duckypad_dir_name, local_dir_name, string_var):
	compare_result = filecmp.dircmp(duckypad_dir_name, local_dir_name, ignore=['keymaps','SYSTEM~1'])
	top_level_to_copy = compare_result.right_only
	top_level_to_remove = compare_result.left_only

	for item in top_level_to_remove:
	    item_path = os.path.join(duckypad_dir_name, item)
	    if "dp_stat" in item_path.lower():
	    	continue
	    # print("removing...", item_path)
	    string_var.set(f'removing: {item_path}')
	    if os.path.isfile(item_path):
	        duckypad_delete_file(item)
	    elif os.path.isdir(item_path):
	        duckypad_delete_dir(item)

	for item in top_level_to_copy:
	    item_path = os.path.join(local_dir_name, item)
	    if os.path.isfile(item_path):
	        # print("copying...", item_path)
	        string_var.set(f'writing: {item_path}')
	        duckypad_open_file_for_writing(item)
	        duckypad_write_file(get_file_content(item_path))
	        duckypad_close_file()
	        continue
	    # this is a dir, create a new dir first
	    # print("creating dir:", item)
	    string_var.set(f'creating dir: {item}')
	    duckypad_create_dir(item)
	    sub_dir_path = [(os.path.join(item_path, x), os.path.join(item, x)) for x in os.listdir(item_path)]
	    my_files = [d for d in sub_dir_path if os.path.isfile(d[0])]
	    for xxx in my_files:
	        file_path = xxx[0]
	        fatfs_path = xxx[1]
	        # print("\tcopying...", fatfs_path)
	        string_var.set(f'writing: {fatfs_path}')
	        duckypad_open_file_for_writing(fatfs_path)
	        duckypad_write_file(get_file_content(file_path))
	        duckypad_close_file()

	for common_dir_name in compare_result.common_dirs:
	    subdir_compare_result = filecmp.dircmp(os.path.join(duckypad_dir_name, common_dir_name), os.path.join(local_dir_name, common_dir_name))
	    
	    subdir_file_to_copy = subdir_compare_result.right_only + subdir_compare_result.diff_files
	    # print("syncing...", common_dir_name)
	    string_var.set(f'writing: {common_dir_name}')

	    for item in subdir_file_to_copy:
	        fatfs_path = os.path.join(common_dir_name, item)
	        file_path = os.path.join(local_dir_name, fatfs_path)
	        # print("\tcopying...", fatfs_path)
	        string_var.set(f'writing: {fatfs_path}')
	        duckypad_open_file_for_writing(fatfs_path)
	        duckypad_write_file(get_file_content(file_path))
	        duckypad_close_file()

	    subdir_file_to_remove = subdir_compare_result.left_only
	    # print("subdir_file_to_remove", subdir_file_to_remove)

	    for item in subdir_file_to_remove:
	        fatfs_path = os.path.join(common_dir_name, item)
	        # print("\tdeleting...", fatfs_path)
	        string_var.set(f'deleting: {fatfs_path}')
	        duckypad_delete_file(fatfs_path)
	# print("done")
	string_var.set(f'done')

def duckypad_hid_sw_reset():
	pc_to_duckypad_buf = [0] * PC_TO_DUCKYPAD_HID_BUF_SIZE
	pc_to_duckypad_buf[0] = 5	# HID Usage ID, always 5
	pc_to_duckypad_buf[1] = 0	# Sequence Number
	pc_to_duckypad_buf[2] = HID_COMMAND_SW_RESET	# Command type
	h.write(pc_to_duckypad_buf)

# sssss = "Extreme E's boat full of race cars has docked in Senegal after kicking off its season in Saudi Arabia (now home of the Dakar Rally), where it's racing this weekend at Lac Rose, the original site of the Dakar. The whole idea of the series is to go off-roading in some of the environments most vulnerable to pollution and climate change caused by humans, with the Ocean X Prix aimed to highlight the problems of over-fishing, sea plastics, destruction of habitats like coral reefs and the million other really bad things we keep putting in the sea."


# start = time.time()
# # duckypad_open_file_for_writing('test.txt')
# # duckypad_write_file(sssss)
# # duckypad_close_file()
# duckypad_delete_dir("/")
# print('took', time.time() - start)

# start = time.time()
# duckypad_hid_init()
# dump_from_hid()
# print('took', time.time() - start)
# h.close()
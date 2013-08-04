from . import native
from ctypes import *

# Convert return codes into exceptions.
class BaconException(Exception):
	pass

def _error_wrapper(fn):
	def f(*args):
		result = fn(*args)
		if result != 0:
			raise BaconException(result) # TODO: format error
	return f

lib = native.load(function_wrapper = _error_wrapper)

# Initialize nativerary now
lib.Init()

BlendFlags = native.BlendFlags
ControllerButtons = native.ControllerButtons
ControllerAxes = native.ControllerAxes

class Shader(object):
	def __init__(self, vertex_source, fragment_source):
		handle = c_int()
		lib.CreateShader(byref(handle), c_char_p(vertex_source), c_char_p(fragment_source))
		self._handle = handle.value

class Image(object):
	def __init__(self, width, height, _handle = None):
		if not _handle:
			_handle = c_int()
			lib.CreateImage(byref(_handle), width, height)
			_handle = _handle.value

		self._handle = _handle
		self._width = width
		self._height = height

	@classmethod
	def load(cls, file, premultiply_alpha = True, discard_bitmap = True):
		flags = 0
		if premultiply_alpha:
			flags |= native.ImageFlags.premultiply_alpha
		if discard_bitmap:
			flags |= native.ImageFlags.discard_bitmap

		handle = c_int()
		lib.LoadImage(byref(handle), bytes(file, 'utf-8'), flags)
		handle = handle.value
		
		width = c_int()
		height = c_int()
		lib.GetImageSize(handle, byref(width), byref(height))
		width = width.value
		height = height.value

		return Image(width, height, handle)

	def unload(self):
		lib.UnloadImage(self._handle)
		self._handle = -1

	@property
	def width(self):
		return self._width

	@property
	def height(self):
		return self._height

class FontMetrics(object):
	def __init__(self, ascent, descent):
		self._ascent = ascent
		self._descent = descent

	@property
	def descent(self):
		return self._descent

	@property
	def ascent(self):
		return self._ascent

class Glyph(object):
	def __init__(self, char, image, offset_x, offset_y, advance):
		self._char = char
		self._image = image
		self._offset_x = offset_x
		self._offset_y = offset_y
		self._advance = advance

	@property
	def char(self):
		return self._char

	@property
	def image(self):
		return self._image

	@property
	def offset_x(self):
		return self._offset_x

	@property
	def offset_y(self):
		return self._offset_y

	@property
	def advance(self):
		return self._advance

class GlyphCache(object):
	def __init__(self, font, size):
		self._glyphs = {}
		self._font = font
		self._size = size

class FontFile(object):
	_font_files = {}

	def __init__(self, file):
		handle = c_int()
		lib.LoadFont(byref(handle), bytes(file, 'utf-8'))
		self._handle = handle.value

	def unload(self):
		lib.UnloadFont(self._handle)
		self._handle = -1

	def get_metrics(self, size):
		ascent = c_float()
		descent = c_float()
		lib.GetFontMetrics(self._handle, size, byref(ascent), byref(descent))
		return FontMetrics(round(ascent.value), round(descent.value))

	def get_glyph(self, size, char):
		image_handle = c_int()
		offset_x = c_float()
		offset_y = c_float()
		advance = c_float()
		lib.GetGlyph(self._handle, size, ord(char), 
			byref(image_handle), byref(offset_x), byref(offset_y), byref(advance))

		width = c_int()
		height = c_int()
		lib.GetImageSize(image_handle, byref(width), byref(height))

		image = Image(width.value, height.value, _handle = image_handle.value)
		return Glyph(char, image, round(offset_x.value), round(offset_y.value), round(advance.value))

	@classmethod
	def get_font_file(cls, file):
		try:
			return cls._font_files[file]
		except KeyError:
			ff = FontFile(file)
			cls._font_files[file] = ff
			return ff

class Font(object):
	def __init__(self, file, size):
		if type(file) is FontFile:
			self._font_file = file
		else:
			self._font_file = FontFile.get_font_file(file)
		self._size = size
		self._glyphs = { }

		self._metrics = self._font_file.get_metrics(size)

	@property
	def metrics(self):
		return self._metrics

	@property
	def ascent(self):
		return self._metrics.ascent

	@property
	def descent(self):
		return self._metrics.descent

	def get_glyph(self, char):
		try:
			return self._glyphs[char]
		except KeyError:
			glyph = self._font_file.get_glyph(self._size, char)
			self._glyphs[char] = glyph
			return glyph

	def get_glyphs(self, str):
		return [self.get_glyph(c) for c in str]

class GlyphLayout(object):
	def __init__(self, glyphs, width=None):
		self.lines = [glyphs]
		# TODO word-wrapping

class Sound(object):
	def __init__(self, file, stream=False):
		flags = 0
		if stream:
			flags |= native.SoundFlags.stream

		if file.lower().endswith('.wav'):
			flags |= native.SoundFlags.format_wav
		elif file.lower().endswith('.ogg'):
			flags |= native.SoundFlags.format_ogg

		handle = c_int()
		lib.LoadSound(byref(handle), bytes(file, 'utf-8'), flags)
		self._handle = handle.value

	def unload(self):
		lib.UnloadSound(self._handle)
		self._handle = -1

	def play(self, gain=None, pan=None, pitch=None):
		if gain is None and pan is None and pitch is None:
			lib.PlaySound(self._handle)
		else:
			voice = Voice(self)
			if gain is not None:
				voice.gain = gain
			if pan is not None:
				voice.pan = pan
			if pitch is not None:
				voice.pitch = pitch
			voice.play()

class Voice(object):
	_gain = 1.0
	_pitch = 1.0
	_pan = 0.0
	_callback = None

	def __init__(self, sound, loop=False):
		flags = 0
		if loop:
			flags |= native.VoiceFlags.loop

		handle = c_int()
		lib.CreateVoice(byref(handle), sound._handle, flags)
		self._handle = handle

	def destroy(self):
		lib.DestroyVoice(self._handle)
		self._handle = -1

	def play(self):
		lib.PlayVoice(self._handle)

	def stop(self):
		lib.StopVoice(self._handle)

	def get_gain(self):
		return self._gain
	def set_gain(self, gain):
		self._gain = gain
		lib.SetVoiceGain(self._handle, gain)
	gain = property(get_gain, set_gain)

	def get_pitch(self):
		return self._pitch
	def set_pitch(self, pitch):
		self._pitch = pitch
		lib.SetVoicePitch(self._handle, pitch)
	pitch = property(get_pitch, set_pitch)

	def get_pan(self):
		return self._pan
	def set_pan(self, pan):
		self._pan = pan
		lib.SetVoicePan(self._handle, pan)
	pan = property(get_pan, set_pan)

	def is_playing(self):
		playing = c_int()
		lib.IsVoicePlaying(self._handle, byref(playing))
		return playing.value
	def set_playing(self, playing):
		if playing:
			self.play()
		else:
			self.stop()
	playing = property(is_playing, set_playing)

	def set_loop_points(self, start_sample=-1, end_sample=0):
		lib.SetVoiceLoopPoints(self._handle, start_sample, end_sample)

	def get_callback(self):
		return self._callback
	def set_callback(self, callback):
		self._callback = callback
		self._callback_handle = lib.VoiceCallback(callback)
		lib.SetVoiceCallback(self._handle, self._callback_handle)
	callback = property(get_callback, set_callback)

	def get_position(self):
		position = c_int()
		lib.GetVoicePosition(self._handle, position)
		return position.value
	def set_position(self, position):
		lib.SetVoicePosition(self._handle, position)
	position = property(get_position, set_position)

'''Version of the Bacon dynamic library that was loaded'''
major_version = c_int()
minor_version = c_int()
patch_version = c_int()
lib.GetVersion(byref(major_version), byref(minor_version), byref(patch_version))
major_version = major_version.value
minor_version = minor_version.value
patch_version = patch_version.value
version = '%d.%d.%d' % (major_version, minor_version, patch_version)

'''Event handler for key events.  Set to a function with the signature:

	def on_key(keyCode, value):
		pass

'''
on_key = None

'''Set of currently pressed keys'''
keys = set()

def _key_event_handler(key, value):
	if value:
		keys.add(key)
	elif key in keys:
		keys.remove(key)

	if on_key:
		on_key(key, value)

'''Event handler for mouse button events.  Set to a function with the signature:

	def on_mouse_button(button, pressed):
		pass
'''
on_mouse_button = None

'''Event handler for mouse scroll events.  Set to a function with the signature:

	def on_mouse_scroll(dx, dy):
		pass
'''
on_mouse_scroll = None

class Mouse(object):
	def __init__(self):
		'''Set of currently pressed buttons'''
		self.button_mask = 0
		self.x = 0
		self.y = 0

	def _update_position(self):
		x = c_float()
		y = c_float()
		lib.GetMousePosition(byref(x), byref(y))
		self.x = x.value
		self.y = y.value

	@property
	def left(self):
		return self.button_mask & (1 << 0)

	@property
	def middle(self):
		return self.button_mask & (1 << 1)

	@property
	def right(self):
		return self.button_mask & (1 << 2)

mouse = Mouse()

def _mouse_button_event_handler(button, value):
	if value:
		mouse.button_mask |= (1 << button)
	else:
		mouse.button_mask &= ~(1 << button)

	if on_mouse_button:
		on_mouse_button(button, value)

def _mouse_scroll_event_handler(dx, dy):
	if on_mouse_scroll:
		on_mouse_scroll(dx, dy)


class Window(object):
	def __init__(self):
		self._width = -1
		self._height = -1
		self._fullscreen = False

	def get_width(self):
		return self._width
	def set_width(self, width):
		lib.SetWindowSize(width, self._height)
		self._width = width
	width = property(get_width, set_width)

	def get_height(self):
		return self._height
	def set_height(self, height):
		lib.SetWindowSize(self._width, height)
		self._height = height
	height = property(get_height, set_height)

	def is_fullscreen(self):
		return self._fullscreen
	def set_fullscreen(self, fullscreen):
		lib.SetWindowFullscreen(fullscreen)
		self._fullscreen = fullscreen
	fullscreen = property(is_fullscreen, set_fullscreen)

window = Window()

on_window_resize = None

def _window_resize_event_handler(width, height):
	window._width = width
	window._height = height
	if on_window_resize:
		on_window_resize(width, height)

def _get_controller_property_string(controller_index, property):
	buffer = lib.create_string_buffer(256)
	length = c_int(lib.sizeof(buffer))
	try:
		lib.GetControllerPropertyString(controller_index, property, buffer, byref(length))
	except:
		return None
	return buffer.value

def _get_controller_property_int(controller_index, property):
	value = c_int()
	try:
		lib.GetControllerPropertyInt(controller_index, property, byref(value))
	except:
		return None
	return value.value
	
class Controller(object):
	def __init__(self, controller_index):
		self._controller_index = controller_index
		
		# Controller state
		self._buttons = 0
		self._axes = {}

		# Controller properties
		self._supported_axes_mask = _get_controller_property_int(controller_index, lib.ControllerProperties.SupportedAxesMask)
		self._supported_buttons_mask = _get_controller_property_int(controller_index, lib.ControllerProperties.SupportedButtonsMask)

		self.vendor_id = _get_controller_property_string(controller_index, lib.ControllerProperties.VendorId)
		self.vendor_id_source = _get_controller_property_string(controller_index, lib.ControllerProperties.VendorIdSource)
		self.product_id = _get_controller_property_string(controller_index, lib.ControllerProperties.ProductId)
		self.version_number = _get_controller_property_string(controller_index, lib.ControllerProperties.VersionNumber)
		self.manufacturer = _get_controller_property_string(controller_index, lib.ControllerProperties.Manufacturer)
		self.product = _get_controller_property_string(controller_index, lib.ControllerProperties.Product)
		self.serial_number = _get_controller_property_string(controller_index, lib.ControllerProperties.SerialNumber)

	def has_axis(self, axis):
		return (axis & self._supported_axes_mask) != 0

	def get_axis(self, axis):
		try:
			return self._axes[axis]
		except KeyError:
			return 0.0

	def has_button(self, button):
		return (button & self._supported_buttons_mask) != 0

	def get_button_state(self, button):
		return (button & self._buttons) != 0

	@property
	def connected(self):
		return self._controller_index is not None

	# Axes

	@property
	def left_thumb_x(self):
		return self.get_axis(lib.ControllerAxes.LeftThumbX)

	@property
	def left_thumb_y(self):
		return self.get_axis(lib.ControllerAxes.LeftThumbY)

	@property
	def right_thumb_x(self):
		return self.get_axis(lib.ControllerAxes.RightThumbX)

	@property
	def right_thumb_y(self):
		return self.get_axis(lib.ControllerAxes.RightThumbY)

	@property
	def left_trigger(self):
		return self.get_axis(lib.ControllerAxes.LeftTrigger)

	@property
	def right_trigger(self):
		return self.get_axis(lib.ControllerAxes.RightTrigger)

	# Buttons

	@property
	def start(self):
		return self._buttons & lib.ControllerButtons.Start

	@property
	def back(self):
		return self._buttons & lib.ControllerButtons.Back

	@property
	def select(self):
		return self._buttons & lib.ControllerButtons.Select

	@property
	def action_up(self):
		return self._buttons & lib.ControllerButtons.ActionUp

	@property
	def action_down(self):
		return self._buttons & lib.ControllerButtons.ActionDown

	@property
	def action_left(self):
		return self._buttons & lib.ControllerButtons.ActionLeft

	@property
	def action_right(self):
		return self._buttons & lib.ControllerButtons.ActionRight

	@property
	def dpad_up(self):
		return self._buttons & lib.ControllerButtons.DpadUp

	@property
	def dpad_down(self):
		return self._buttons & lib.ControllerButtons.DpadDown

	@property
	def dpad_left(self):
		return self._buttons & lib.ControllerButtons.DpadLeft

	@property
	def dpad_right(self):
		return self._buttons & lib.ControllerButtons.DpadRight

	@property
	def left_shoulder(self):
		return self._buttons & lib.ControllerButtons.LeftShoulder

	@property
	def right_shoulder(self):
		return self._buttons & lib.ControllerButtons.RightShoulder

	@property
	def left_thumb(self):
		return self._buttons & lib.ControllerButtons.LeftThumb

	@property
	def right_thumb(self):
		return self._buttons & lib.ControllerButtons.RightThumb

'''Event handler for game controller connected:

	def on_controller_connected(controller):
		pass
	bacon.on_controller_connected = on_controller_connected
'''
on_controller_connected = None

'''Event handler for game controller connected:

	def on_controller_connected(controller):
		pass
	bacon.on_controller_connected = on_controller_connected
'''
on_controller_disconnected = None

on_controller_button = None

on_controller_axis = None

# Map controller index to controller
_controllers = {}

def _controller_connected_event_handler(controller_index, connected):
	# Invalidate any existing controller with the same index
	controller = None
	try:
		controller = _controllers[controller_index]
		controller._controller_index = None
	except KeyError:
		pass

	if connected:
		_controllers[controller_index] = controller = Controller(controller_index)
		if on_controller_connected:
			on_controller_connected(controller)
	else:
		del _controllers[controller_index]
		if on_controller_disconnected:
			on_controller_disconnected(controller)
		
def _controller_button_event_handler(controller_index, button, pressed):
	try:
		controller = _controllers[controller_index]
	except KeyError:
		return

	if pressed:
		controller._buttons |= button
	else:
		controller._buttons &= ~button

	if on_controller_button:
		on_controller_button(controller, button, pressed)

def _controller_axis_event_handler(controller_index, axis, value):	
	try:
		controller = _controllers[controller_index]
	except KeyError:
		return

	controller._axes[axis] = value

	if on_controller_axis:
		on_controller_axis(controller, axis, value)


def _on_tick_default():
	clear(1, 0, 0, 1)
	# TODO: useful message

'''Tick callback.  This function must be implemented and is called once per frame;
it is where your game performs both its update and rendering:

	def on_tick():
		pass
	bacon.tick = on_tick
'''
on_tick = _on_tick_default

def _tick_callback():
	mouse._update_position()
	on_tick()

# API
def run():
	# Window handler
	window_resize_callback_handle = lib.WindowResizeEventHandler(_window_resize_event_handler)
	lib.SetWindowResizeEventHandler(window_resize_callback_handle)

	# Key handler
	key_callback_handle = lib.KeyEventHandler(_key_event_handler)
	lib.SetKeyEventHandler(key_callback_handle)

	# Mouse handlers
	mouse_button_callback_handle = lib.MouseButtonEventHandler(_mouse_button_event_handler)
	lib.SetMouseButtonEventHandler(mouse_button_callback_handle)
	mouse_scroll_callback_handle = lib.MouseScrollEventHandler(_mouse_scroll_event_handler)
	lib.SetMouseScrollEventHandler(mouse_scroll_callback_handle)

	# Controller handlers
	controller_connected_handle = lib.ControllerConnectedEventHandler(_controller_connected_event_handler)
	lib.SetControllerConnectedEventHandler(controller_connected_handle)
	controller_button_handle = lib.ControllerButtonEventHandler(_controller_button_event_handler)
	lib.SetControllerButtonEventHandler(controller_button_handle)
	controller_axis_handle = lib.ControllerAxisEventHandler(_controller_axis_event_handler)
	lib.SetControllerAxisEventHandler(controller_axis_handle)

	# Tick handler
	tick_callback_handle = lib.TickCallback(_tick_callback)
	lib.SetTickCallback(tick_callback_handle)

	lib.Run()

	lib.SetWindowResizeEventHandler(None)
	lib.SetKeyEventHandler(None)
	lib.SetMouseButtonEventHandler(None)
	lib.SetMouseScrollEventHandler(None)
	lib.SetControllerConnectedEventHandler(None)
	lib.SetControllerButtonEventHandler(None)
	lib.SetControllerAxisEventHandler(None)
	lib.SetTickCallback(None)
	
# Graphics
push_transform = lib.PushTransform
pop_transform = lib.PopTransform
translate = lib.Translate
scale = lib.Scale
rotate = lib.Rotate
def set_transform(matrix):
	lib.SetTransform((c_float * 16)(*matrix))

push_color = lib.PushColor
pop_color = lib.PopColor
set_color = lib.SetColor
multiply_color = lib.MultiplyColor

clear = lib.Clear
def set_frame_buffer(image):
	lib.SetFrameBuffer(image._handle)
set_viewport = lib.SetViewport
def set_shader(shader):
	lib.SetShader(shader._handle)
set_blending = lib.SetBlending
def draw_image(image, x1, y1, x2 = None, y2 = None):
	if x2 is None:
		x2 = x1 + image.width
	if y2 is None:
		y2 = y1 + image.height
	lib.DrawImage(image._handle, x1, y1, x2, y2)
def draw_image_region(image, x1, y1, x2, y2,
					  ix1, iy1, ix2, iy2):
	lib.DrawImage(image._handle, x1, y1, x2, y2, ix1, iy1, ix2, iy2)
draw_line = lib.DrawLine

def draw_string(font, text, x, y):
	glyphs = font.get_glyphs(text)
	glyph_layout = GlyphLayout(glyphs)
	draw_glyph_layout(glyph_layout, x, y)

def draw_glyph_layout(glyph_layout, x, y):
	start_x = x
	for line in glyph_layout.lines:
		x = start_x
		for glyph in line:
			draw_image(glyph.image, x + glyph.offset_x, y - glyph.offset_y)
			x += glyph.advance

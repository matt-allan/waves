"""ctypes bindings to libsameboy."""

import ctypes
import pathlib

# ---------------------------------------------------------------------------
# Opaque pointer type
# ---------------------------------------------------------------------------

GB_gameboy_p = ctypes.c_void_p

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GB_MODEL_DMG_B = 0x002

# GB_key_t enum values (from Core/joypad.h)
GB_KEY_RIGHT = 0
GB_KEY_LEFT = 1
GB_KEY_UP = 2
GB_KEY_DOWN = 3
GB_KEY_A = 4
GB_KEY_B = 5
GB_KEY_SELECT = 6
GB_KEY_START = 7

# ---------------------------------------------------------------------------
# Structs
# ---------------------------------------------------------------------------


class GB_sample_t(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int16),
        ("right", ctypes.c_int16),
    ]


# ---------------------------------------------------------------------------
# Callback types (ctypes.CFUNCTYPE uses cdecl, matching SameBoy)
# ---------------------------------------------------------------------------

RGB_ENCODE_FUNC = ctypes.CFUNCTYPE(
    ctypes.c_uint32,  # return
    GB_gameboy_p,  # gb
    ctypes.c_uint8,  # r
    ctypes.c_uint8,  # g
    ctypes.c_uint8,  # b
)

VBLANK_FUNC = ctypes.CFUNCTYPE(
    None,
    GB_gameboy_p,
    ctypes.c_int,  # GB_vblank_type_t (C enum = int)
)

LOG_FUNC = ctypes.CFUNCTYPE(
    None,
    GB_gameboy_p,
    ctypes.c_char_p,  # const char *
    ctypes.c_int,  # GB_log_attributes_t (C enum = int)
)

AUDIO_SAMPLE_FUNC = ctypes.CFUNCTYPE(
    None,
    GB_gameboy_p,
    ctypes.POINTER(GB_sample_t),
)

SERIAL_BIT_START_FUNC = ctypes.CFUNCTYPE(
    None,
    GB_gameboy_p,
    ctypes.c_bool,  # bit_to_send
)

SERIAL_BIT_END_FUNC = ctypes.CFUNCTYPE(
    ctypes.c_bool,  # returned bit
    GB_gameboy_p,
)

# ---------------------------------------------------------------------------
# Library loader
# ---------------------------------------------------------------------------

_DEFAULT_LIB_PATH = (
    pathlib.Path(__file__).resolve().parent.parent.parent / "build" / "lib"
)


def load(lib_path: str | None = None):
    """Load libsameboy and set all argtypes/restypes.

    *lib_path* is the path to ``libsameboy.so`` (or ``.dylib``).  When
    *None* the default build output location is searched.
    """
    if lib_path is None:
        for ext in (".so", ".dylib"):
            p = _DEFAULT_LIB_PATH / ("libsameboy" + ext)
            if p.exists():
                lib_path = str(p)
                break
        if lib_path is None:
            raise FileNotFoundError(f"libsameboy not found in {_DEFAULT_LIB_PATH}")

    lib = ctypes.CDLL(str(lib_path))

    # -- Lifecycle --
    lib.GB_alloc.restype = GB_gameboy_p
    lib.GB_alloc.argtypes = []

    lib.GB_init.restype = GB_gameboy_p
    lib.GB_init.argtypes = [GB_gameboy_p, ctypes.c_int]

    lib.GB_dealloc.restype = None
    lib.GB_dealloc.argtypes = [GB_gameboy_p]

    # -- User data --
    lib.GB_set_user_data.restype = None
    lib.GB_set_user_data.argtypes = [GB_gameboy_p, ctypes.c_void_p]

    lib.GB_get_user_data.restype = ctypes.c_void_p
    lib.GB_get_user_data.argtypes = [GB_gameboy_p]

    # -- ROM loading --
    lib.GB_load_rom.restype = ctypes.c_int
    lib.GB_load_rom.argtypes = [GB_gameboy_p, ctypes.c_char_p]

    lib.GB_load_boot_rom.restype = ctypes.c_int
    lib.GB_load_boot_rom.argtypes = [GB_gameboy_p, ctypes.c_char_p]

    lib.GB_load_boot_rom_from_buffer.restype = None
    lib.GB_load_boot_rom_from_buffer.argtypes = [
        GB_gameboy_p,
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_size_t,
    ]

    # -- Execution --
    lib.GB_run_frame.restype = ctypes.c_uint64
    lib.GB_run_frame.argtypes = [GB_gameboy_p]

    # -- Video --
    lib.GB_set_pixels_output.restype = None
    lib.GB_set_pixels_output.argtypes = [
        GB_gameboy_p,
        ctypes.POINTER(ctypes.c_uint32),
    ]

    lib.GB_set_rgb_encode_callback.restype = None
    lib.GB_set_rgb_encode_callback.argtypes = [GB_gameboy_p, RGB_ENCODE_FUNC]

    lib.GB_set_vblank_callback.restype = None
    lib.GB_set_vblank_callback.argtypes = [GB_gameboy_p, VBLANK_FUNC]

    # -- Audio --
    lib.GB_set_sample_rate.restype = None
    lib.GB_set_sample_rate.argtypes = [GB_gameboy_p, ctypes.c_uint]

    lib.GB_apu_set_sample_callback.restype = None
    lib.GB_apu_set_sample_callback.argtypes = [
        GB_gameboy_p,
        AUDIO_SAMPLE_FUNC,
    ]

    # -- Serial --
    lib.GB_set_serial_transfer_bit_start_callback.restype = None
    lib.GB_set_serial_transfer_bit_start_callback.argtypes = [
        GB_gameboy_p,
        SERIAL_BIT_START_FUNC,
    ]

    lib.GB_set_serial_transfer_bit_end_callback.restype = None
    lib.GB_set_serial_transfer_bit_end_callback.argtypes = [
        GB_gameboy_p,
        SERIAL_BIT_END_FUNC,
    ]

    # -- Logging --
    lib.GB_set_log_callback.restype = None
    lib.GB_set_log_callback.argtypes = [GB_gameboy_p, LOG_FUNC]

    # -- Joypad --
    lib.GB_set_key_state.restype = None
    lib.GB_set_key_state.argtypes = [GB_gameboy_p, ctypes.c_int, ctypes.c_bool]

    return lib

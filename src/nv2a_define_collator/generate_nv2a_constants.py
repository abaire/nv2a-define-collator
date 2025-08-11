from __future__ import annotations

# ruff: noqa: T201 `print` found
import argparse
import hashlib
import importlib.resources as pkg_resources
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import requests
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

SOURCES = [
    "https://raw.githubusercontent.com/XboxDev/nxdk/refs/heads/master/lib/pbkit/nv_regs.h",
    "https://raw.githubusercontent.com/xemu-project/xemu/refs/heads/master/hw/xbox/nv2a/nv2a_regs.h",
    "https://raw.githubusercontent.com/Ryzee119/LithiumX/cbea9330527597dc5201423141a8a02e0ab900cd/src/libs/xgu/nv2a_regs.h",
]

PACKED_SHORT_COMMANDS = {
    "NV062_SET_PITCH": ("Source", "Destination"),
    "NV097_ARRAY_ELEMENT16": ("V0", "V1"),
    "NV097_SET_CLEAR_RECT_HORIZONTAL": ("Min", "Max"),
    "NV097_SET_CLEAR_RECT_VERTICAL": ("Min", "Max"),
    "NV097_SET_SURFACE_CLIP_HORIZONTAL": ("Offset", "Size"),
    "NV097_SET_SURFACE_CLIP_VERTICAL": ("Offset", "Size"),
    "NV097_SET_SURFACE_PITCH": ("Color", "Zeta"),
    "NV097_SET_TEXCOORD0_2S": ("U", "V"),
    "NV097_SET_TEXCOORD1_2S": ("U", "V"),
    "NV097_SET_TEXCOORD2_2S": ("U", "V"),
    "NV097_SET_TEXCOORD3_2S": ("U", "V"),
    "NV097_SET_TEXTURE_IMAGE_RECT": ("H", "W"),
    "NV097_SET_WINDOW_CLIP_HORIZONTAL": ("Offset", "Size"),
    "NV097_SET_WINDOW_CLIP_VERTICAL": ("Offset", "Size"),
    "NV09F_CONTROL_POINT_IN": ("X", "Y"),
    "NV09F_CONTROL_POINT_OUT": ("X", "Y"),
    "NV09F_SIZE": ("W", "H"),
}

BOOLEAN_VALUE_COMMANDS = {
    "NV097_SET_ALPHA_TEST_ENABLE",
    "NV097_SET_BLEND_ENABLE",
    "NV097_SET_CULL_FACE_ENABLE",
    "NV097_SET_DEPTH_TEST_ENABLE",
    "NV097_SET_DITHER_ENABLE",
    "NV097_SET_FOG_ENABLE",
    "NV097_SET_LIGHTING_ENABLE",
    "NV097_SET_LINE_SMOOTH_ENABLE",
    "NV097_SET_POINT_PARAMS_ENABLE",
    "NV097_SET_POINT_SMOOTH_ENABLE",
    "NV097_SET_POLY_OFFSET_FILL_ENABLE",
    "NV097_SET_POLY_OFFSET_LINE_ENABLE",
    "NV097_SET_POLY_OFFSET_POINT_ENABLE",
    "NV097_SET_POLY_SMOOTH_ENABLE",
    "NV097_SET_SPECULAR_ENABLE",
    "NV097_SET_STENCIL_TEST_ENABLE",
    "NV097_SET_TEXTURE_MATRIX_ENABLE",
}

FLOAT_VALUE_COMMANDS = {
    "NV097_ARRAY_ELEMENT16",
    "NV097_ARRAY_ELEMENT32",
    "NV097_DRAW_ARRAYS",
    "NV097_INLINE_ARRAY",
    "NV097_SET_BACK_LIGHT_AMBIENT_COLOR",
    "NV097_SET_BACK_LIGHT_DIFFUSE_COLOR",
    "NV097_SET_BACK_LIGHT_SPECULAR_COLOR",
    "NV097_SET_BACK_MATERIAL_ALPHA",
    "NV097_SET_BACK_MATERIAL_EMISSION",
    "NV097_SET_BACK_SCENE_AMBIENT_COLOR",
    "NV097_SET_BACK_SPECULAR_PARAMS",
    "NV097_SET_CLIP_MAX",
    "NV097_SET_CLIP_MIN",
    "NV097_SET_COMPOSITE_MATRIX",
    "NV097_SET_DIFFUSE_COLOR3F",
    "NV097_SET_DIFFUSE_COLOR4F",
    "NV097_SET_EYE_POSITION",
    "NV097_SET_EYE_VECTOR",
    "NV097_SET_FOG_COORD",
    "NV097_SET_FOG_PARAMS",
    "NV097_SET_FOG_PLANE",
    "NV097_SET_INVERSE_MODEL_VIEW_MATRIX",
    "NV097_SET_LIGHT_AMBIENT_COLOR",
    "NV097_SET_LIGHT_DIFFUSE_COLOR",
    "NV097_SET_LIGHT_INFINITE_DIRECTION",
    "NV097_SET_LIGHT_INFINITE_HALF_VECTOR",
    "NV097_SET_LIGHT_LOCAL_ATTENUATION",
    "NV097_SET_LIGHT_LOCAL_POSITION",
    "NV097_SET_LIGHT_LOCAL_RANGE",
    "NV097_SET_LIGHT_SPECULAR_COLOR",
    "NV097_SET_LIGHT_SPOT_DIRECTION",
    "NV097_SET_LIGHT_SPOT_FALLOFF",
    "NV097_SET_MATERIAL_ALPHA",
    "NV097_SET_MATERIAL_EMISSION",
    "NV097_SET_MODEL_VIEW_MATRIX",
    "NV097_SET_NORMAL3F",
    "NV097_SET_POINT_PARAMS",
    "NV097_SET_PROJECTION_MATRIX",
    "NV097_SET_SCENE_AMBIENT_COLOR",
    "NV097_SET_SPECULAR_COLOR3F",
    "NV097_SET_SPECULAR_COLOR4F",
    "NV097_SET_SPECULAR_PARAMS",
    "NV097_SET_TEXCOORD0_2F",
    "NV097_SET_TEXCOORD0_4F",
    "NV097_SET_TEXCOORD1_2F",
    "NV097_SET_TEXCOORD1_4F",
    "NV097_SET_TEXCOORD2_2F",
    "NV097_SET_TEXCOORD2_4F",
    "NV097_SET_TEXCOORD3_2F",
    "NV097_SET_TEXCOORD3_4F",
    "NV097_SET_TEXTURE_MATRIX",
    "NV097_SET_TRANSFORM_CONSTANT",
    "NV097_SET_TRANSFORM_DATA",
    "NV097_SET_VERTEX3F",
    "NV097_SET_VERTEX4F",
    "NV097_SET_VERTEX_DATA2F_M",
    "NV097_SET_VERTEX_DATA4F_M",
    "NV097_SET_VIEWPORT_OFFSET",
    "NV097_SET_VIEWPORT_SCALE",
    "NV097_SET_WEIGHT1F",
    "NV097_SET_WEIGHT2F",
    "NV097_SET_WEIGHT3F",
    "NV097_SET_WEIGHT4F",
}

CUSTOM_PROCESSOR_COMMANDS = {
    "NV097_SET_COLOR_MASK": "_process_color_mask",
    "NV097_SET_COLOR_MATERIAL": "_process_set_color_material",
    "NV097_SET_COMBINER_ALPHA_ICW": "_process_combiner_icw",
    "NV097_SET_COMBINER_ALPHA_OCW": "_process_combiner_alpha_ocw",
    "NV097_SET_COMBINER_COLOR_ICW": "_process_combiner_icw",
    "NV097_SET_COMBINER_COLOR_OCW": "_process_combiner_color_ocw",
    "NV097_SET_COMBINER_CONTROL": "_process_combiner_control",
    "NV097_SET_COMBINER_FACTOR0": "_process_combiner_color_factor",
    "NV097_SET_COMBINER_FACTOR1": "_process_combiner_color_factor",
    "NV097_SET_COMBINER_SPECULAR_FOG_CW0": "_process_combiner_specular_fog_cw0",
    "NV097_SET_COMBINER_SPECULAR_FOG_CW1": "_process_combiner_specular_fog_cw1",
    "NV097_SET_CONTROL0": "_process_set_control0",
    "NV097_DRAW_ARRAYS": "_process_draw_arrays",
    "NV097_SET_LIGHT_CONTROL": "_process_set_light_control",
    "NV097_SET_LIGHT_ENABLE_MASK": "_process_set_light_enable_mask",
    "NV097_SET_TEXGEN_S": "_process_set_texgen_rst",
    "NV097_SET_TEXGEN_T": "_process_set_texgen_rst",
    "NV097_SET_TEXGEN_R": "_process_set_texgen_rst",
    "NV097_SET_TEXGEN_Q": "_process_set_texgen_q",
    "NV097_SET_SHADER_OTHER_STAGE_INPUT": "_process_set_other_stage_input",
    "NV097_SET_SHADER_STAGE_PROGRAM": "process_shader_stage_program",
    "NV097_SET_SPECULAR_FOG_FACTOR": "_process_combiner_color_factor",
    "NV097_SET_SURFACE_FORMAT": "_process_set_surface_format",
    "NV097_SET_TEXTURE_ADDRESS": "_process_set_texture_address",
    "NV097_SET_TEXTURE_CONTROL0": "_process_set_texture_control0",
    "NV097_SET_TEXTURE_CONTROL1": "_process_set_texture_control1",
    "NV097_SET_TEXTURE_FILTER": "_process_set_texture_filter",
    "NV097_SET_TEXTURE_FORMAT": "_process_set_texture_format",
    "NV097_SET_TEXTURE_PALETTE": "_process_set_texture_palette",
    "NV097_SET_VERTEX_DATA_ARRAY_FORMAT": "_process_vertex_data_array_format",
}

ARRAY_COMMANDS = {
    "NV097_SET_BACK_MATERIAL_EMISSION": (4, 3),
    "NV097_SET_BACK_SCENE_AMBIENT_COLOR": (4, 3),
    "NV097_SET_BACK_SPECULAR_PARAMS": (4, 6),
    "NV097_SET_COLOR_KEY_COLOR": (4, 4),
    "NV097_SET_COMBINER_ALPHA_ICW": (4, 8),
    "NV097_SET_COMBINER_ALPHA_OCW": (4, 8),
    "NV097_SET_COMBINER_COLOR_ICW": (4, 8),
    "NV097_SET_COMBINER_COLOR_OCW": (4, 8),
    "NV097_SET_COMBINER_FACTOR0": (4, 8),
    "NV097_SET_COMBINER_FACTOR1": (4, 8),
    "NV097_SET_COMPOSITE_MATRIX": (4, 16),
    "NV097_SET_EYE_POSITION": (4, 4),
    "NV097_SET_EYE_VECTOR": (4, 3),
    "NV097_SET_FOG_PARAMS": (4, 3),
    "NV097_SET_FOG_PLANE": (4, 4),
    "NV097_SET_MATERIAL_EMISSION": (4, 3),
    "NV097_SET_NORMAL3F": (4, 3),
    "NV097_SET_POINT_PARAMS": (4, 8),
    "NV097_SET_PROJECTION_MATRIX": (4, 16),
    "NV097_SET_SCENE_AMBIENT_COLOR": (4, 3),
    "NV097_SET_SPECULAR_FOG_FACTOR": (4, 2),
    "NV097_SET_SPECULAR_PARAMS": (4, 6),
    "NV097_SET_STIPPLE_PATTERN": (4, 32),
    "NV097_SET_TEXGEN_Q": (16, 4),
    "NV097_SET_TEXGEN_R": (16, 4),
    "NV097_SET_TEXGEN_S": (16, 4),
    "NV097_SET_TEXGEN_T": (16, 4),
    "NV097_SET_TEXTURE_ADDRESS": (0x40, 4),
    "NV097_SET_TEXTURE_BORDER_COLOR": (0x40, 4),
    "NV097_SET_TEXTURE_CONTROL0": (0x40, 4),
    "NV097_SET_TEXTURE_CONTROL1": (0x40, 4),
    "NV097_SET_TEXTURE_FILTER": (0x40, 4),
    "NV097_SET_TEXTURE_FORMAT": (0x40, 4),
    "NV097_SET_TEXTURE_IMAGE_RECT": (0x40, 4),
    "NV097_SET_TEXTURE_MATRIX_ENABLE": (4, 4),
    "NV097_SET_TEXTURE_OFFSET": (0x40, 4),
    "NV097_SET_TEXTURE_PALETTE": (0x40, 4),
    "NV097_SET_TEXTURE_SET_BUMP_ENV_OFFSET": (0x40, 4),
    "NV097_SET_TEXTURE_SET_BUMP_ENV_SCALE": (0x40, 4),
    "NV097_SET_TRANSFORM_CONSTANT": (4, 32),
    "NV097_SET_TRANSFORM_DATA": (4, 4),
    "NV097_SET_TRANSFORM_PROGRAM": (4, 32),
    "NV097_SET_VERTEX3F": (4, 3),
    "NV097_SET_VERTEX4F": (4, 4),
    "NV097_SET_VERTEX_DATA2F_M": (4, 32),
    "NV097_SET_VERTEX_DATA2S": (4, 16),
    "NV097_SET_VERTEX_DATA4F_M": (4, 64),
    "NV097_SET_VERTEX_DATA4UB": (4, 16),
    "NV097_SET_VERTEX_DATA_ARRAY_FORMAT": (4, 16),
    "NV097_SET_VERTEX_DATA_ARRAY_OFFSET": (4, 16),
    "NV097_SET_VIEWPORT_OFFSET": (4, 4),
    "NV097_SET_VIEWPORT_SCALE": (4, 4),
    "NV097_SET_WEIGHT2F": (4, 2),
    "NV097_SET_WEIGHT3F": (4, 3),
    "NV097_SET_WEIGHT4F": (4, 4),
}

STRUCT_ARRAY_COMMANDS = {
    "NV097_SET_BACK_LIGHT_AMBIENT_COLOR": (64, 8, 4, 3),
    "NV097_SET_BACK_LIGHT_DIFFUSE_COLOR": (64, 8, 4, 3),
    "NV097_SET_BACK_LIGHT_SPECULAR_COLOR": (64, 8, 4, 3),
    "NV097_SET_INVERSE_MODEL_VIEW_MATRIX": (64, 4, 4, 16),
    "NV097_SET_LIGHT_AMBIENT_COLOR": (128, 8, 4, 3),
    "NV097_SET_LIGHT_DIFFUSE_COLOR": (128, 8, 4, 3),
    "NV097_SET_LIGHT_INFINITE_DIRECTION": (128, 8, 4, 3),
    "NV097_SET_LIGHT_INFINITE_HALF_VECTOR": (128, 8, 4, 3),
    "NV097_SET_LIGHT_LOCAL_ATTENUATION": (128, 8, 4, 3),
    "NV097_SET_LIGHT_LOCAL_POSITION": (128, 8, 4, 3),
    "NV097_SET_LIGHT_LOCAL_RANGE": (128, 8, 4, 1),
    "NV097_SET_LIGHT_SPECULAR_COLOR": (128, 8, 4, 3),
    "NV097_SET_LIGHT_SPOT_DIRECTION": (128, 8, 4, 4),
    "NV097_SET_LIGHT_SPOT_FALLOFF": (128, 8, 4, 3),
    "NV097_SET_MODEL_VIEW_MATRIX": (64, 4, 4, 16),
    "NV097_SET_TEXGEN_PLANE_Q": (64, 4, 4, 4),
    "NV097_SET_TEXGEN_PLANE_R": (64, 4, 4, 4),
    "NV097_SET_TEXGEN_PLANE_S": (64, 4, 4, 4),
    "NV097_SET_TEXGEN_PLANE_T": (64, 4, 4, 4),
    "NV097_SET_TEXTURE_MATRIX": (64, 4, 4, 16),
    "NV097_SET_TEXTURE_SET_BUMP_ENV_MAT": (0x40, 4, 4, 4),
}

# The simple heuristic to attempt to differentiate bitvector values from masks fails in certain cases where a sibling
# value is a suffix of another sibling. E.g., "NV062_SET_COLOR_FORMAT_LE_X8R8G8B8_Z8R8G8B8" is a sibling of
# "NV062_SET_COLOR_FORMAT_LE_X8R8G8B8" and will be incorrectly associated as a bitvector value instead of a top level
# value.
#
# Other comamnds may look like children but are not: e.g., NV097_SET_TRANSFORM_PROGRAM_LOAD and
# NV097_SET_TRANSFORM_PROGRAM. Setting the parent to "" here suppresses the child association.
CHILD_ASSOCIATION_OVERRIDE: dict[str, str] = {
    "NV062_SET_COLOR_FORMAT_LE_X8R8G8B8_Z8R8G8B8": "NV062_SET_COLOR_FORMAT",
    "NV097_SET_CULL_FACE_ENABLE": "",
    "NV097_SET_LOGIC_OP_ENABLE": "",
    "NV097_SET_POINT_PARAMS_ENABLE": "",
    "NV097_SET_STENCIL_FUNC_MASK": "",
    "NV097_SET_STENCIL_FUNC_REF": "",
    "NV097_SET_TEXTURE_MATRIX_ENABLE": "",
    "NV097_SET_TRANSFORM_CONSTANT_LOAD": "",
    "NV097_SET_TRANSFORM_PROGRAM_CXT_WRITE_EN": "",
    "NV097_SET_TRANSFORM_PROGRAM_LOAD": "",
    "NV097_SET_TRANSFORM_PROGRAM_START": "",
}

CUSTOM_NAMES = {
    (0x97, 0x1720): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__POS",
    (0x97, 0x1724): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__WEIGHT",
    (0x97, 0x1728): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__NORMAL",
    (0x97, 0x172C): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__DIFFUSE",
    (0x97, 0x1730): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__SPECULAR",
    (0x97, 0x1734): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__FOG_COORD",
    (0x97, 0x1738): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__POINT_SIZE",
    (0x97, 0x173C): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__BACK_DIFFUSE",
    (0x97, 0x1740): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__BACK_SPECULAR",
    (0x97, 0x1744): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__TEX0",
    (0x97, 0x1748): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__TEX1",
    (0x97, 0x174C): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__TEX2",
    (0x97, 0x1750): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__TEX3",
    (0x97, 0x1754): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__13",
    (0x97, 0x1758): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__14",
    (0x97, 0x175C): "NV097_SET_VERTEX_DATA_ARRAY_OFFSET__15",
    (0x97, 0x1760): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__POS",
    (0x97, 0x1764): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__WEIGHT",
    (0x97, 0x1768): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__NORMAL",
    (0x97, 0x176C): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__DIFFUSE",
    (0x97, 0x1770): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__SPECULAR",
    (0x97, 0x1774): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__FOG_COORD",
    (0x97, 0x1778): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__POINT_SIZE",
    (0x97, 0x177C): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__BACK_DIFFUSE",
    (0x97, 0x1780): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__BACK_SPECULAR",
    (0x97, 0x1784): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__TEX0",
    (0x97, 0x1788): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__TEX1",
    (0x97, 0x178C): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__TEX2",
    (0x97, 0x1790): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__TEX3",
    (0x97, 0x1794): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__13",
    (0x97, 0x1798): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__14",
    (0x97, 0x179C): "NV097_SET_VERTEX_DATA_ARRAY_FORMAT__15",
    (0x97, 0x1940): "NV097_SET_VERTEX_DATA4UB[pos]",
    (0x97, 0x1944): "NV097_SET_VERTEX_DATA4UB[weights]",
    (0x97, 0x1948): "NV097_SET_VERTEX_DATA4UB[normal]",
    (0x97, 0x194C): "NV097_SET_VERTEX_DATA4UB[diffuse]",
    (0x97, 0x1950): "NV097_SET_VERTEX_DATA4UB[specular]",
    (0x97, 0x1954): "NV097_SET_VERTEX_DATA4UB[fog_coord]",
    (0x97, 0x1958): "NV097_SET_VERTEX_DATA4UB[point_size]",
    (0x97, 0x195C): "NV097_SET_VERTEX_DATA4UB[back_diffuse]",
    (0x97, 0x1960): "NV097_SET_VERTEX_DATA4UB[back_specular]",
    (0x97, 0x1964): "NV097_SET_VERTEX_DATA4UB[tex0]",
    (0x97, 0x1968): "NV097_SET_VERTEX_DATA4UB[tex1]",
    (0x97, 0x196C): "NV097_SET_VERTEX_DATA4UB[tex2]",
    (0x97, 0x1970): "NV097_SET_VERTEX_DATA4UB[tex3]",
    (0x97, 0x1974): "NV097_SET_VERTEX_DATA4UB[13]",
    (0x97, 0x1978): "NV097_SET_VERTEX_DATA4UB[14]",
    (0x97, 0x197C): "NV097_SET_VERTEX_DATA4UB[15]",
}


def _name_sequential_operations(nv_class: int, nv_op_base: int, stride: int, elements: list[str]):
    offset = 0
    for i, op_name in enumerate(elements):
        CUSTOM_NAMES[(nv_class, nv_op_base + offset)] = f"{op_name}[{i}]"
        offset += stride


_name_sequential_operations(
    0x97,
    0x1880,
    4,
    [
        "NV097_SET_VERTEX_DATA2F_M[pos][x]",
        "NV097_SET_VERTEX_DATA2F_M[pos][y]",
        "NV097_SET_VERTEX_DATA2F_M[weights][0]",
        "NV097_SET_VERTEX_DATA2F_M[weights][1]",
        "NV097_SET_VERTEX_DATA2F_M[normal][x]",
        "NV097_SET_VERTEX_DATA2F_M[normal][y]",
        "NV097_SET_VERTEX_DATA2F_M[diffuse][r]",
        "NV097_SET_VERTEX_DATA2F_M[diffuse][g]",
        "NV097_SET_VERTEX_DATA2F_M[specular][r]",
        "NV097_SET_VERTEX_DATA2F_M[specular][g]",
        "NV097_SET_VERTEX_DATA2F_M[fog_coord][0]",
        "NV097_SET_VERTEX_DATA2F_M[fog_coord][1]",
        "NV097_SET_VERTEX_DATA2F_M[point_size][0]",
        "NV097_SET_VERTEX_DATA2F_M[point_size][1]",
        "NV097_SET_VERTEX_DATA2F_M[back_diffuse][r]",
        "NV097_SET_VERTEX_DATA2F_M[back_diffuse][g]",
        "NV097_SET_VERTEX_DATA2F_M[back_specular][r]",
        "NV097_SET_VERTEX_DATA2F_M[back_specular][g]",
        "NV097_SET_VERTEX_DATA2F_M[tex0][u]",
        "NV097_SET_VERTEX_DATA2F_M[tex0][v]",
        "NV097_SET_VERTEX_DATA2F_M[tex1][u]",
        "NV097_SET_VERTEX_DATA2F_M[tex1][v]",
        "NV097_SET_VERTEX_DATA2F_M[tex2][u]",
        "NV097_SET_VERTEX_DATA2F_M[tex2][v]",
        "NV097_SET_VERTEX_DATA2F_M[tex3][u]",
        "NV097_SET_VERTEX_DATA2F_M[tex3][v]",
        "NV097_SET_VERTEX_DATA2F_M[13][0]",
        "NV097_SET_VERTEX_DATA2F_M[13][1]",
        "NV097_SET_VERTEX_DATA2F_M[14][0]",
        "NV097_SET_VERTEX_DATA2F_M[14][1]",
        "NV097_SET_VERTEX_DATA2F_M[15][0]",
        "NV097_SET_VERTEX_DATA2F_M[15][1]",
    ],
)
_name_sequential_operations(
    0x97,
    0x1900,
    4,
    [
        "NV097_SET_VERTEX_DATA2S[pos][x|y]",
        "NV097_SET_VERTEX_DATA2S[weights][0|1]",
        "NV097_SET_VERTEX_DATA2S[normal][x|y]",
        "NV097_SET_VERTEX_DATA2S[diffuse][r|g]",
        "NV097_SET_VERTEX_DATA2S[specular][r|g]",
        "NV097_SET_VERTEX_DATA2S[fog_coord][0|1]",
        "NV097_SET_VERTEX_DATA2S[point_size][0|1]",
        "NV097_SET_VERTEX_DATA2S[back_diffuse][r|g]",
        "NV097_SET_VERTEX_DATA2S[back_specular][r|g]",
        "NV097_SET_VERTEX_DATA2S[tex0][u|v]",
        "NV097_SET_VERTEX_DATA2S[tex1][u|v]",
        "NV097_SET_VERTEX_DATA2S[tex2][u|v]",
        "NV097_SET_VERTEX_DATA2S[tex3][u|v]",
        "NV097_SET_VERTEX_DATA2S[13][0|1]",
        "NV097_SET_VERTEX_DATA2S[14][0|1]",
        "NV097_SET_VERTEX_DATA2S[15][0|1]",
    ],
)
_name_sequential_operations(
    0x97,
    0x1980,
    4,
    [
        "NV097_SET_VERTEX_DATA4S_M[pos][x|y]",
        "NV097_SET_VERTEX_DATA4S_M[pos][z|w]",
        "NV097_SET_VERTEX_DATA4S_M[weights][0|1]",
        "NV097_SET_VERTEX_DATA4S_M[weights][2|3]",
        "NV097_SET_VERTEX_DATA4S_M[normal][x|y]",
        "NV097_SET_VERTEX_DATA4S_M[normal][z|w]",
        "NV097_SET_VERTEX_DATA4S_M[diffuse][r|g]",
        "NV097_SET_VERTEX_DATA4S_M[diffuse][b|a]",
        "NV097_SET_VERTEX_DATA4S_M[specular][r|g]",
        "NV097_SET_VERTEX_DATA4S_M[specular][b|a]",
        "NV097_SET_VERTEX_DATA4S_M[fog_coord][0|1]",
        "NV097_SET_VERTEX_DATA4S_M[fog_coord][2|3]",
        "NV097_SET_VERTEX_DATA4S_M[point_size][0|1]",
        "NV097_SET_VERTEX_DATA4S_M[point_size][2|3]",
        "NV097_SET_VERTEX_DATA4S_M[back_diffuse][r|g]",
        "NV097_SET_VERTEX_DATA4S_M[back_diffuse][b|a]",
        "NV097_SET_VERTEX_DATA4S_M[back_specular][r|g]",
        "NV097_SET_VERTEX_DATA4S_M[back_specular][b|a]",
        "NV097_SET_VERTEX_DATA4S_M[tex0][u|v]",
        "NV097_SET_VERTEX_DATA4S_M[tex0][2|3]",
        "NV097_SET_VERTEX_DATA4S_M[tex1][u|v]",
        "NV097_SET_VERTEX_DATA4S_M[tex1][2|3]",
        "NV097_SET_VERTEX_DATA4S_M[tex2][u|v]",
        "NV097_SET_VERTEX_DATA4S_M[tex2][2|3]",
        "NV097_SET_VERTEX_DATA4S_M[tex3][u|v]",
        "NV097_SET_VERTEX_DATA4S_M[tex3][2|3]",
        "NV097_SET_VERTEX_DATA4S_M[13][0|1]",
        "NV097_SET_VERTEX_DATA4S_M[13][2|3]",
        "NV097_SET_VERTEX_DATA4S_M[14][0|1]",
        "NV097_SET_VERTEX_DATA4S_M[14][2|3]",
        "NV097_SET_VERTEX_DATA4S_M[15][0|1]",
        "NV097_SET_VERTEX_DATA4S_M[15][2|3]",
    ],
)
_name_sequential_operations(
    0x97,
    0x1A00,
    4,
    [
        "NV097_SET_VERTEX_DATA4F_M[pos][x]",
        "NV097_SET_VERTEX_DATA4F_M[pos][y]",
        "NV097_SET_VERTEX_DATA4F_M[pos][z]",
        "NV097_SET_VERTEX_DATA4F_M[pos][w]",
        "NV097_SET_VERTEX_DATA4F_M[weights][0]",
        "NV097_SET_VERTEX_DATA4F_M[weights][1]",
        "NV097_SET_VERTEX_DATA4F_M[weights][2]",
        "NV097_SET_VERTEX_DATA4F_M[weights][3]",
        "NV097_SET_VERTEX_DATA4F_M[normal][x]",
        "NV097_SET_VERTEX_DATA4F_M[normal][y]",
        "NV097_SET_VERTEX_DATA4F_M[normal][z]",
        "NV097_SET_VERTEX_DATA4F_M[normal][w]",
        "NV097_SET_VERTEX_DATA4F_M[diffuse][r]",
        "NV097_SET_VERTEX_DATA4F_M[diffuse][g]",
        "NV097_SET_VERTEX_DATA4F_M[diffuse][b]",
        "NV097_SET_VERTEX_DATA4F_M[diffuse][a]",
        "NV097_SET_VERTEX_DATA4F_M[specular][r]",
        "NV097_SET_VERTEX_DATA4F_M[specular][g]",
        "NV097_SET_VERTEX_DATA4F_M[specular][b]",
        "NV097_SET_VERTEX_DATA4F_M[specular][a]",
        "NV097_SET_VERTEX_DATA4F_M[fog_coord][0]",
        "NV097_SET_VERTEX_DATA4F_M[fog_coord][1]",
        "NV097_SET_VERTEX_DATA4F_M[fog_coord][2]",
        "NV097_SET_VERTEX_DATA4F_M[fog_coord][3]",
        "NV097_SET_VERTEX_DATA4F_M[point_size][0]",
        "NV097_SET_VERTEX_DATA4F_M[point_size][1]",
        "NV097_SET_VERTEX_DATA4F_M[point_size][2]",
        "NV097_SET_VERTEX_DATA4F_M[point_size][3]",
        "NV097_SET_VERTEX_DATA4F_M[back_diffuse][r]",
        "NV097_SET_VERTEX_DATA4F_M[back_diffuse][g]",
        "NV097_SET_VERTEX_DATA4F_M[back_diffuse][b]",
        "NV097_SET_VERTEX_DATA4F_M[back_diffuse][a]",
        "NV097_SET_VERTEX_DATA4F_M[back_specular][r]",
        "NV097_SET_VERTEX_DATA4F_M[back_specular][g]",
        "NV097_SET_VERTEX_DATA4F_M[back_specular][b]",
        "NV097_SET_VERTEX_DATA4F_M[back_specular][a]",
        "NV097_SET_VERTEX_DATA4F_M[tex0][u]",
        "NV097_SET_VERTEX_DATA4F_M[tex0][v]",
        "NV097_SET_VERTEX_DATA4F_M[tex0][2]",
        "NV097_SET_VERTEX_DATA4F_M[tex0][3]",
        "NV097_SET_VERTEX_DATA4F_M[tex1][u]",
        "NV097_SET_VERTEX_DATA4F_M[tex1][v]",
        "NV097_SET_VERTEX_DATA4F_M[tex1][2]",
        "NV097_SET_VERTEX_DATA4F_M[tex1][3]",
        "NV097_SET_VERTEX_DATA4F_M[tex2][u]",
        "NV097_SET_VERTEX_DATA4F_M[tex2][v]",
        "NV097_SET_VERTEX_DATA4F_M[tex2][2]",
        "NV097_SET_VERTEX_DATA4F_M[tex2][3]",
        "NV097_SET_VERTEX_DATA4F_M[tex3][u]",
        "NV097_SET_VERTEX_DATA4F_M[tex3][v]",
        "NV097_SET_VERTEX_DATA4F_M[tex3][2]",
        "NV097_SET_VERTEX_DATA4F_M[tex3][3]",
        "NV097_SET_VERTEX_DATA4F_M[13][0]",
        "NV097_SET_VERTEX_DATA4F_M[13][1]",
        "NV097_SET_VERTEX_DATA4F_M[13][2]",
        "NV097_SET_VERTEX_DATA4F_M[13][3]",
        "NV097_SET_VERTEX_DATA4F_M[14][0]",
        "NV097_SET_VERTEX_DATA4F_M[14][1]",
        "NV097_SET_VERTEX_DATA4F_M[14][2]",
        "NV097_SET_VERTEX_DATA4F_M[14][3]",
        "NV097_SET_VERTEX_DATA4F_M[15][0]",
        "NV097_SET_VERTEX_DATA4F_M[15][1]",
        "NV097_SET_VERTEX_DATA4F_M[15][2]",
        "NV097_SET_VERTEX_DATA4F_M[15][3]",
    ],
)

_NUMERIC_VALUE = r"(?:0[x|X])?[0-9a-fA-F]+"
PREFIXED_HEX_VALUE_RE = re.compile(r"(0[x|X][0-9a-fA-F]+)\s*$")
BITSHIFT_VALUE_RE = re.compile(r"\(?(" + _NUMERIC_VALUE + r")\s*<<\s*(" + _NUMERIC_VALUE + r")\)?\s*$")
RAW_INT_VALUE_RE = re.compile(r"(\d+)\s*$")
PGRAPH_COMMAND_RE = re.compile(r"^#(\s*)define\s+(NV0[^\s]+)\s+(.*)")


@dataclass
class PGRAPHCommand:
    name: str
    raw_value: str
    numeric_value: int | None

    @property
    def special_parser_name(self) -> str:
        """Returns the name of a custom parser function used to process the values for this command."""
        camel_name = _to_camel_case(self.name)
        return f"Parse{camel_name}"


PGRAPHCommandTree = dict[str, tuple[PGRAPHCommand, dict[int, tuple[PGRAPHCommand, dict[int, PGRAPHCommand]]]]]

EXTRAS: PGRAPHCommandTree = {
    # https://github.com/xemu-project/xemu/issues/711
    "NV097_SET_OCCLUDE_ZSTENCIL_EN": (PGRAPHCommand("NV097_SET_OCCLUDE_ZSTENCIL_EN", "0x00001D84", 0x00001D84), {}),
    # https://github.com/xemu-project/xemu/issues/702
    "NV097_SET_SWATH_WIDTH": (PGRAPHCommand("NV097_SET_SWATH_WIDTH", "0x000009F8", 0x000009F8), {}),
}


def _get_artifact_path(url: str, output_dir: Path) -> tuple[Path, str]:
    filename = url.split("/")[-1]
    url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]
    unique_filename = f"{url_hash}_{filename}"
    return output_dir / unique_filename, filename


def _fetch_files(output_dir: Path, *, force_update: bool) -> int:
    for url in SOURCES:
        file_path, filename = _get_artifact_path(url, output_dir)

        if force_update or not file_path.exists():
            try:
                response = requests.get(url, timeout=10)
                response.raise_for_status()

                file_path.write_bytes(response.content)
                print(f"[{filename}]: ✅ Downloaded from {url} successfully", file=sys.stderr)

            except requests.exceptions.RequestException as e:
                print(f"[{filename}]: ❌ Failed: {e}", file=sys.stderr)
                return 1
    return 0


def _extract_numeric_value(value_string: str) -> int | None:
    match = PREFIXED_HEX_VALUE_RE.match(value_string)
    if match:
        return int(match.group(1), 16)

    match = BITSHIFT_VALUE_RE.match(value_string)
    if match:
        return int(match.group(1), base=0) << int(match.group(2), base=0)

    match = RAW_INT_VALUE_RE.match(value_string)
    if match:
        return int(match.group(1))

    return None


def _handle_special_case_value(pgraph_command) -> int | None:
    if pgraph_command == "NV097_SET_CONTROL0_Z_FORMAT_FLOAT":
        return 1 << 12

    if pgraph_command == "NV097_SET_LINE_WIDTH_MASK":
        return (64 << 3) - 1

    return None


def _sanitize_name(command_name: str) -> list[str]:
    """Expands special cases where value defines apply across multiple commands."""

    # Stencil op values apply across the three stencil op commands but are only specified once in the header.
    if command_name.startswith("NV097_SET_STENCIL_OP_V"):
        suffix = command_name[22:]
        return [
            prefix + suffix
            for prefix in ("NV097_SET_STENCIL_OP_FAIL", "NV097_SET_STENCIL_OP_ZFAIL", "NV097_SET_STENCIL_OP_ZPASS")
        ]

    # TODO: Fix spelling upstream.
    if command_name == "NV097_SET_STIPPLE_PATERN_0":
        return ["NV097_SET_STIPPLE_PATTERN"]

    return [command_name]


def _process_header(file_path: Path) -> list[PGRAPHCommand]:
    command_list = []

    with open(file_path) as infile:
        for line in infile:
            if not line.startswith("#"):
                continue

            match = PGRAPH_COMMAND_RE.match(line)
            if not match:
                continue

            symbol_names = _sanitize_name(match.group(2))
            raw_value = match.group(3)
            value = _extract_numeric_value(raw_value)
            if value is None:
                value = _handle_special_case_value(symbol_names[0])
                if value is None:
                    print(f"[{file_path}]: Failed to parse value from '{line.strip()}'", file=sys.stderr)

            command_list.extend(
                [PGRAPHCommand(name=symbol, raw_value=raw_value, numeric_value=value) for symbol in symbol_names]
            )

    return command_list


def _map_children_to_parents(all_names: dict[str, list[str]]) -> dict[str, str]:
    min_len = min(len(components) for components in all_names.values())

    child_to_parent_map = {}
    for name, components in all_names.items():
        if len(components) <= min_len:
            continue

        parent_name = CHILD_ASSOCIATION_OVERRIDE.get(name)
        if parent_name:
            child_to_parent_map[name] = parent_name
            continue
        if parent_name is not None:
            continue

        for i in range(len(components) - 1, min_len - 1, -1):
            parent_name = "_".join(components[:i])
            if parent_name in all_names:
                child_to_parent_map[name] = parent_name
                break

    return child_to_parent_map


def _build_command_tree(all_commands: list[PGRAPHCommand]) -> PGRAPHCommandTree:
    name_to_command = {cmd.name: cmd for cmd in all_commands}
    all_names = {name: name.split("_") for name in name_to_command}

    child_to_parent_map = _map_children_to_parents(all_names)

    parent_to_children_list: dict[str, list[str]] = {}
    for child, parent in child_to_parent_map.items():
        parent_to_children_list.setdefault(parent, []).append(child)

    top_level_names = set(all_names.keys()) - set(child_to_parent_map.keys())

    pgraph_map = {}
    for grandparent_name in top_level_names:
        grandparent_cmd = name_to_command[grandparent_name]
        children_map = {}

        immediate_children = parent_to_children_list.get(grandparent_name, [])
        for child_name in immediate_children:
            child_cmd = name_to_command[child_name]
            if child_cmd.numeric_value is None:
                continue

            grandchildren_map = {}
            grandchildren = parent_to_children_list.get(child_name, [])
            for grandchild_name in grandchildren:
                grandchild_cmd = name_to_command[grandchild_name]
                if grandchild_cmd.numeric_value is not None:
                    grandchildren_map[grandchild_cmd.numeric_value] = grandchild_cmd

            children_map[child_cmd.numeric_value] = (child_cmd, grandchildren_map)

        pgraph_map[grandparent_name] = (grandparent_cmd, children_map)

    return pgraph_map


def _to_camel_case(snake_case_name: str) -> str:
    return "".join(part.capitalize() for part in snake_case_name.split("_"))


def _build_flat_constants_list(command_tree: PGRAPHCommandTree) -> list[str]:
    entries = []
    for command, _ in command_tree.values():
        if command.numeric_value is None:
            continue

        entries.append(f"{command.name} = 0x{command.numeric_value:X}")

    return sorted(entries)


def _build_name_map(command_tree: PGRAPHCommandTree) -> list[str]:
    entries = {}
    for command, _ in command_tree.values():
        if command.numeric_value is None:
            continue

        try:
            prefix_str = command.name.split("_")[0]
            class_prefix = int(prefix_str[2:], 16)
        except (ValueError, IndexError):
            continue

        entries[(class_prefix, command.numeric_value)] = command.name

    for key, value in CUSTOM_NAMES.items():
        entries[key] = value

    return sorted([f'(0x{key[0]:X}, 0x{key[1]:X}): "{value}"' for key, value in entries.items()])


def _build_processor_map(command_tree: PGRAPHCommandTree) -> list[str]:
    nested_map: dict[int, dict[int, list[PGRAPHCommand]]] = {}

    has_special_parser = set()

    for command, children in command_tree.values():
        if command.numeric_value is None:
            continue

        if children:
            has_special_parser.add(command.name)

        try:
            prefix_str = command.name.split("_")[0]
            class_prefix = int(prefix_str[2:], 16)
        except (ValueError, IndexError):
            continue

        class_map = nested_map.setdefault(class_prefix, {})
        class_map.setdefault(command.numeric_value, []).append(command)

    result = []
    for class_prefix in sorted(nested_map.keys()):
        result.append(f"    0x{class_prefix:X}: {{")
        class_map = nested_map[class_prefix]

        for op_code in sorted(class_map.keys()):
            commands = sorted(class_map[op_code], key=lambda x: x.name)
            first_command = commands[0]
            name = first_command.name
            processor_key = name

            if name in CUSTOM_PROCESSOR_COMMANDS:
                parser = CUSTOM_PROCESSOR_COMMANDS[name]
            elif name in FLOAT_VALUE_COMMANDS:
                parser = "_process_float_param"
            elif name in BOOLEAN_VALUE_COMMANDS:
                parser = "_process_boolean_param"
            elif name in PACKED_SHORT_COMMANDS:
                low_label, high_label = PACKED_SHORT_COMMANDS[name]
                parser = f'_generate_process_double_uint16("{low_label}", "{high_label}")'
            elif name in has_special_parser:
                parser = first_command.special_parser_name
            else:
                parser = "_process_passthrough"

            if name in STRUCT_ARRAY_COMMANDS:
                struct_stride, struct_count, field_size, field_count = STRUCT_ARRAY_COMMANDS[name]
                processor_key = (
                    f"StructStateArray({name}, 0x{struct_stride:X}, {struct_count}, 0x{field_size:X}, {field_count})"
                )
            elif name in ARRAY_COMMANDS:
                stride, count = ARRAY_COMMANDS[name]
                processor_key = f"StateArray({name}, 0x{stride:X}, {count})"

            result.append(f"        {processor_key}: {parser},")

        result.append("    },")

    return result


def _build_value_parser(
    parent_command: PGRAPHCommand, children_map: dict[int, tuple[PGRAPHCommand, dict[int, PGRAPHCommand]]]
) -> list[str]:
    characters_to_remove = len(f"{parent_command.name}_")

    result = ["    _VALUES = {"]

    for value in sorted(children_map):
        value_info, _ = children_map[value]
        symbolic_name = value_info.name[characters_to_remove:]
        result.append(f'      {value}: "{symbolic_name}",')
    result.append("    }")
    result.append("    ret = _VALUES.get(nv_param)")
    result.append("    if ret:")
    result.append("      return ret")
    result.append('    return f"0x{nv_param:X}?"')

    return result


def _build_bitfield_parser(grandparent_cmd: PGRAPHCommand, children_map: dict) -> list[str]:
    result = ["    results: list[str] = []"]

    prefix_to_remove = f"{grandparent_cmd.name}_"
    for child_cmd, grandchildren_map in children_map.values():
        if child_cmd.numeric_value is None:
            continue

        child_short_name = child_cmd.name[: len(prefix_to_remove)]
        mask_hex = f"0x{child_cmd.numeric_value:X}"

        result.append(f"    field_val = nv_param & {mask_hex}")
        fallback_value = f"results.append(f'{child_short_name}:0x{{field_val:X}}')"

        if not grandchildren_map:
            result.append(f"    {fallback_value}")
        else:
            result.append("    field_map = {")
            for grandchild_val, grandchild_cmd in grandchildren_map.items():
                result.append(f'        0x{grandchild_val:X}: "{grandchild_cmd.name}",')
            result.extend(
                [
                    "    }",
                    "    if field_val in field_map:",
                    "        grandchild_name = field_map[field_val]",
                    f"        symbolic_part = grandchild_name.replace('{prefix_to_remove}', '', 1)",
                    "        results.append(symbolic_part.replace('_', ':', 1))",
                    "    else:",
                    f"        {fallback_value}",
                ]
            )

    result.append("    return f'{{{', '.join(results)}}}'")

    return result


def _build_parser_functions(command_tree: PGRAPHCommandTree) -> list[str]:
    parsers_to_generate = []
    for name, (_, children_map) in sorted(command_tree.items()):
        if name in CUSTOM_PROCESSOR_COMMANDS:
            continue

        if children_map:
            parsers_to_generate.append(name)

    result = []
    for i, name in enumerate(parsers_to_generate):
        if i > 0:
            result.append("\n")

        grandparent_cmd, children_map = command_tree[name]
        has_grandchildren = any(gc_map for _, gc_map in children_map.values())

        result.append(f"def {grandparent_cmd.special_parser_name}(_nv_class, _nv_op, nv_param: int) -> str:")
        result.append(f'    """Parses the components of a {name} command."""')

        if not has_grandchildren:
            result.extend(_build_value_parser(grandparent_cmd, children_map))
        else:
            result.extend(_build_bitfield_parser(grandparent_cmd, children_map))

    return result


def _generate_python_file(command_tree: PGRAPHCommandTree, env: Environment) -> str:
    template_context = {
        "FLAT_CONSTANTS": _build_flat_constants_list(command_tree),
        "NAME_MAP": _build_name_map(command_tree),
        "PROCESSOR_MAP": _build_processor_map(command_tree),
        "PARSERS": _build_parser_functions(command_tree),
    }

    ret = []
    templates = [
        "header.py.jinja2",
        "color_combiner_processors.py.jinja2",
        "generic_processors.py.jinja2",
        "lighting_processors.py.jinja2",
        "shader_processors.py.jinja2",
        "texture_processors.py.jinja2",
        "nv2a_constants.py.jinja2",
    ]
    for template_name in templates:
        template = env.get_template(template_name)
        ret.append(template.render(template_context))

    return "\n".join(ret)


def _merge_new_commands(all_commands: PGRAPHCommandTree, new_commands: PGRAPHCommandTree):
    for command_name, command in new_commands.items():
        if command_name in all_commands:
            logger.debug("Skipping duplicate command '%s'", command_name)
            continue

        all_commands[command_name] = command


def _get_jinja2_env() -> Environment:
    try:
        template_dir_path = pkg_resources.files("nv2a_define_collator") / "templates"
    except ModuleNotFoundError:
        script_dir = Path(__file__).parent
        template_dir_path = script_dir / "templates"

    return Environment(loader=FileSystemLoader(str(template_dir_path)), autoescape=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download header files from remote sources.")
    parser.add_argument("--update", action="store_true", help="Update cached headers")
    parser.add_argument(
        "-v",
        "--verbose",
        help="Enables verbose logging information",
        action="store_true",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="filename",
        help="Writes output to the given file instead of stdout",
    )
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    output_dir = Path("../../headers")
    output_dir.mkdir(exist_ok=True)

    ret = _fetch_files(output_dir, force_update=args.update)
    if ret:
        return ret

    all_commands: PGRAPHCommandTree = {}

    for url in SOURCES:
        file_path, _filename = _get_artifact_path(url, output_dir)
        commands = _process_header(file_path)
        command_tree = _build_command_tree(commands)
        _merge_new_commands(all_commands, command_tree)

    _merge_new_commands(all_commands, EXTRAS)

    output = _generate_python_file(all_commands, _get_jinja2_env())

    if args.output:
        with open(args.output, "w") as outfile:
            outfile.write(output)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())

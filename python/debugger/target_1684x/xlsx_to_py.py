# ==============================================================================
#
# Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
#
# TPU-MLIR is licensed under the 2-Clause BSD License except for the
# third-party components.
#
# ==============================================================================

from time import gmtime, strftime
import re
import numpy as np
import pandas
import numpy
from jinja2 import Template

match_illegal = re.compile("[（）& /()]")

ctype_template_str = """
class {{class_name}}_reg(cmd_base_reg):
    OP_NAME = "{{op_name}}"
    _fields_ = [{% for field, field_length in fields %}
        ("{{field}}", ctypes.c_uint64, {{field_length}}),
        {%- endfor %}
    ]
    {% for key in valid_key %}
    {{key}}: int
    {%- endfor %}

    length: int = {{length}}

    {% for raw, valid in invalid_key %}
    @property
    def {{valid}}(self) -> int:
        return self["{{raw}}"]
    {%- endfor %}
"""


def pd_to_dict(df):
    # filter out invalid recorder
    valid = ~df.iloc[:, 1].isnull()
    df = df[valid].copy()
    fields = list(df.iloc[:, 0])
    fields = [
        i.replace("des_", "").replace("short_", "").replace("opt_", "") for i in fields
    ]
    return list(zip(fields, numpy.cumsum(df.iloc[:, 1].astype(int))))


tiu_reg_a2 = "./BM1688_TPU_TIU_Reg6.5.xlsx"
dma_reg_a2 = "./GDMA_1688_DES_REG_v7.7.xlsx"

bdc_sheet_name = [
    "AR",
    "CMP",
    "CONV",
    "LAR",
    "LIN",
    "MM",
    "MM2",
    "PorD",
    "RQ&DQ",
    "SEG",
    "SFU",
    "SG",
    "SGL",
    "SYS",
    "SYSID",
    "TRANS&BC",
    "VC",
    "sAR",
    "sCMP",
    "sCONV",
    "sLIN",
    "sMM",
    "sMM2",
    "sPorD",
    "sRQ&sDQ",
    "sSEG",
    "sSFU",
    "sSG",
    "sSGL",
    "sTRANS&sBC",
    "sVC",
]
dma_sheet_name = [
    "DMA_cw_transpose",
    "DMA_gather",
    "DMA_general",
    "DMA_masked_select",
    "DMA_matrix",
    "DMA_nonzero",
    "DMA_scatter",
    "DMA_tensor（0x000）",
    "sDMA_general",
    "sDMA_masked_select ",
    "sDMA_matrix",
    "sDMA_nonzero",
    "sDMA_sys",
]

reg_bdc = pandas.read_excel(tiu_reg_a2, sheet_name=bdc_sheet_name)
reg_dma = pandas.read_excel(dma_reg_a2, sheet_name=dma_sheet_name)

cmd_reg = {}
for k, df in reg_bdc.items():
    cmd_reg[k] = pd_to_dict(df)

for k, df in reg_dma.items():
    cmd_reg[k] = pd_to_dict(df)

file_head = f"""# ==============================================================================
#
# Copyright (C) 2022 Sophgo Technologies Inc.  All rights reserved.
#
# TPU-MLIR is licensed under the 2-Clause BSD License except for the
# third-party components.
#
# ==============================================================================
#
# automatically generated by {__file__}
# time: {strftime('%Y-%m-%d %H:%M:%S', gmtime())}
# this file should not be changed except format.
# tiu_reg_fn: {tiu_reg_a2}
# dma_reg_fn: {dma_reg_a2}

from typing import Dict, Type
import ctypes
from ..target_common import cmd_base_reg

"""


tail_template_str = """

op_class_dic: Dict[str, Type[cmd_base_reg]] = {
    {% for cmd_type, class_name in cmd %}
    "{{cmd_type}}": {{class_name}}_reg,$
    {%- endfor %}
}
"""


with open("regdef.py", "w") as fb:
    fb.write(file_head)
    # fb.write("reg_def_obj = ")
    # fb.write(pprint.pformat(cmd_reg, width=80))
    ctype_template = Template(ctype_template_str)
    file_end_template = Template(tail_template_str)

    ctype_py_str = []

    cmds = []
    for key in cmd_reg:
        cmd_reg_def = cmd_reg[key]

        field_keys, high_bits = zip(*cmd_reg_def)
        if all(64 * x in high_bits for x in range(1, high_bits[-1] // 64 + 1)):
            bits_width = np.diff(high_bits, prepend=0)
            fields = [(k, l) for k, l in zip(field_keys, bits_width)]

            valid_key = [match_illegal.sub("_", key) for key in field_keys]
            invalid_key = [
                (key, match_illegal.sub("_", key))
                for key in field_keys
                if match_illegal.search(key)
            ]

            print(match_illegal.sub("_", key))
            ctype_py_str.append(
                ctype_template.render(
                    op_name=key,
                    class_name=match_illegal.sub("_", key),
                    fields=fields,
                    valid_key=valid_key,
                    invalid_key=invalid_key,
                    length=high_bits[-1],
                )
            )
            cmds.append((key, match_illegal.sub("_", key)))

    fb.write(("\n").join(ctype_py_str))
    fb.write(file_end_template.render(cmd=cmds))
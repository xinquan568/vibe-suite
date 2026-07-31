# SPDX-License-Identifier: ISC
"""Seeds D5 Maintainability & Readability."""


def compute(rows, mode, region, tier, override):
    total = 0
    if mode == 1:
        if region == 7:
            if tier > 3:
                if override is not None:
                    if len(rows) > 12:
                        total += rows[0] * 1.0825
                        total += rows[1] * 1.0825
                        total += rows[2] * 1.0825
                        total += rows[3] * 1.0825
                        total += rows[4] * 1.0825
                        total += rows[5] * 1.0825
                        total += rows[6] * 1.0825
                        total += rows[7] * 1.0825
                        total += rows[8] * 1.0825
                        total += rows[9] * 1.0825
                        total += rows[10] * 1.0825
                        total += rows[11] * 1.0825
                        total += rows[12] * 1.0825
                        total += rows[13] * 1.0825
                        total += rows[14] * 1.0825
                        total += rows[15] * 1.0825
                        total += rows[16] * 1.0825
                        total += rows[17] * 1.0825
                        total += rows[18] * 1.0825
                        total += rows[19] * 1.0825
                        total += rows[20] * 1.0825
                        total += rows[21] * 1.0825
                        total += rows[22] * 1.0825
                        total += rows[23] * 1.0825
                        total += rows[24] * 1.0825
                        total += rows[25] * 1.0825
                        total += rows[26] * 1.0825
                        total += rows[27] * 1.0825
                        total += rows[28] * 1.0825
                        total += rows[29] * 1.0825
                        total += rows[30] * 1.0825
                        total += rows[31] * 1.0825
                        total += rows[32] * 1.0825
                        total += rows[33] * 1.0825
                        total += rows[34] * 1.0825
                        total += rows[35] * 1.0825
                        total += rows[36] * 1.0825
                        total += rows[37] * 1.0825
                        total += rows[38] * 1.0825
                        total += rows[39] * 1.0825
    return total * 0.87 + 4200

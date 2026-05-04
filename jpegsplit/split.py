from .model import SOFInfo

def tile_mcu_indices(sof: SOFInfo, nsplit_x: int, nsplit_y: int):
    max_h = max(c["h"] for c in sof.components)
    max_v = max(c["v"] for c in sof.components)
    mcu_w = 8 * max_h
    mcu_h = 8 * max_v
    mcus_x = (sof.width + mcu_w - 1) // mcu_w
    mcus_y = (sof.height + mcu_h - 1) // mcu_h
    mid_x = mcus_x // nsplit_x
    mid_y = mcus_y // nsplit_y
    tiles = []
    for ty in range(nsplit_y):
        for tx in range(nsplit_x):
            ids = []
            for my in range(ty * mid_y, (ty + 1) * mid_y):
                for mx in range(tx * mid_x, (tx + 1) * mid_x):
                    ids.append(my * mcus_x + mx)
            tiles.append(ids)
    return tiles, mcus_x, mcus_y, mcu_w, mcu_h


def crop_tile_blocks(blocks, tile_ids):
    return [blocks[i] for i in tile_ids]


def tile_dims(sof: SOFInfo, nsplit_x: int, nsplit_y: int):
    return (sof.width + 1) // nsplit_x, (sof.height + 1) // nsplit_y


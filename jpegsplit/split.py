from .model import SOFInfo

def round_tile_size(tile_size: int, quantum: int = 16) -> int:
    if tile_size < 1:
        raise ValueError("tile_size must be a positive integer")
    return ((tile_size + quantum - 1) // quantum) * quantum


def _tiling_plan(sof: SOFInfo, tile_size: int):
    max_h = max(c["h"] for c in sof.components)
    max_v = max(c["v"] for c in sof.components)
    mcu_w = 8 * max_h
    mcu_h = 8 * max_v
    mcus_x = (sof.width + mcu_w - 1) // mcu_w
    mcus_y = (sof.height + mcu_h - 1) // mcu_h
    rounded_tile_size = round_tile_size(tile_size)
    tile_mcus_x = max(1, (rounded_tile_size + mcu_w - 1) // mcu_w)
    tile_mcus_y = max(1, (rounded_tile_size + mcu_h - 1) // mcu_h)
    tiles_x = (mcus_x + tile_mcus_x - 1) // tile_mcus_x
    tiles_y = (mcus_y + tile_mcus_y - 1) // tile_mcus_y

    return {
        "mcus_x": mcus_x,
        "mcus_y": mcus_y,
        "mcu_w": mcu_w,
        "mcu_h": mcu_h,
        "tile_mcus_x": tile_mcus_x,
        "tile_mcus_y": tile_mcus_y,
        "tiles_x": tiles_x,
        "tiles_y": tiles_y,
    }


def tile_mcu_indices(sof: SOFInfo, tile_size: int):
    plan = _tiling_plan(sof, tile_size)
    tiles = []
    for ty in range(plan["tiles_y"]):
        start_my = ty * plan["tile_mcus_y"]
        end_my = min(start_my + plan["tile_mcus_y"], plan["mcus_y"])
        for tx in range(plan["tiles_x"]):
            start_mx = tx * plan["tile_mcus_x"]
            end_mx = min(start_mx + plan["tile_mcus_x"], plan["mcus_x"])
            ids = []
            for my in range(start_my, end_my):
                for mx in range(start_mx, end_mx):
                    ids.append(my * plan["mcus_x"] + mx)
            tiles.append(ids)
    return tiles, plan["tiles_x"], plan["tiles_y"], plan["mcu_w"], plan["mcu_h"]


def crop_tile_blocks(blocks, tile_ids):
    return [blocks[i] for i in tile_ids]


def tile_dims(sof: SOFInfo, tile_size: int):
    plan = _tiling_plan(sof, tile_size)
    dims = []
    tile_w = plan["tile_mcus_x"] * plan["mcu_w"]
    tile_h = plan["tile_mcus_y"] * plan["mcu_h"]
    for ty in range(plan["tiles_y"]):
        y0 = ty * tile_h
        for tx in range(plan["tiles_x"]):
            x0 = tx * tile_w
            dims.append((min(tile_w, sof.width - x0), min(tile_h, sof.height - y0)))
    return dims


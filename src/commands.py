from dataclasses import dataclass
from enum import Enum


class ItemSlot(Enum):
    WEAPON_MAINHAND = "weapon.mainhand"
    WEAPON_OFFHAND = "weapon.offhand"
    ARMOR_CHEST = "armor.chest"
    ARMOR_FEET = "armor.feet"
    ARMOR_HEAD = "armor.head"
    ARMOR_LEGS = "armor.legs"
    CONTAINER = "container"
    ENDERCHEST = "enderchest"
    HOTBAR = "hotbar"
    INVENTORY = "inventory"
    HORSE_SADDLE = "horse.saddle"
    HORSE_CHEST = "horse.chest"
    HORSE_ARMOR = "horse.armor"

    change_version = "1.17"

    # Returns item_slot.slotNo if version is 1.17+ else slot.item_slot.slotNo
    def get_value_by_version(self, game_version, slot_id: int = None):
        if game_version >= self.change_version.value:
            if slot_id is None:
                return self.value
            else:
                return self.value + '.' + str(slot_id)
        else:
            return "slot." + self.value + (" " + str(slot_id) if slot_id is not None else " 0")


# Supports minecraft 1.13+
@dataclass
class ReplaceItemCommand:
    # x, y and z coordinates, space separated
    block_pos: str = None
    # Target entity is either block or @a, @e etc.
    target_entity: str = None
    slot: ItemSlot = None
    slotId: int = None
    item: str = None
    count: int = None

    change_version_one = "1.17"

    # If in the future new changes are made to the command, add the new structure here.
    def command_by_game_version(self, game_version):
        if game_version >= self.change_version_one:
            if self.target_entity != "block":
                return "item replace entity " \
                       + self.target_entity \
                       + " " \
                       + self.slot.get_value_by_version(game_version) \
                       + " with " \
                       + self.item \
                       + (" " + str(self.count) if self.count is not None else "")
            else:
                return "item replace block " \
                       + self.block_pos \
                       + self.slot.get_value_by_version(game_version) \
                       + " with " \
                       + self.item \
                       + (" " + str(self.count) if self.count is not None else "")

        else:
            if self.target_entity != "block":
                return "replaceitem entity " \
                       + self.target_entity \
                       + " "  \
                       + self.slot.get_value_by_version(game_version, self.slotId) \
                       + " " \
                       + self.item \
                       + (" " + str(self.count) if self.count is not None else "")
            else:
                return "replaceitem block " \
                       + self.block_pos \
                       + " " \
                       + self.slot.get_value_by_version(game_version, self.slotId) \
                       + " " \
                       + self.item \
                       + (" " + str(self.count) if self.count is not None else "")
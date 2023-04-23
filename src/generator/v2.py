# -*- coding: utf-8 -*-
#
#Infinite Music Discs generator module implementation
#Generation tool, datapack design, and resourcepack design by link2_thepast
#
#Generates datapack v2.0

import os
import json
import shutil
import zipfile

from src.definitions import Constants, Helpers, Status, DiscListContents
from src.commands import ReplaceItemCommand, ItemSlot

from src.generator.base import VirtualGenerator



class GeneratorV2(VirtualGenerator):

    def generate_datapack(self, entry_list: DiscListContents, user_settings={}):

        #read settings
        pack_format = user_settings.get('version').get('dp', Constants.DEFAULT_PACK_FORMAT)
        offset = user_settings.get('offset', 0)

        datapack_name = user_settings.get('name', Constants.DEFAULT_PACK_NAME)
        datapack_name = datapack_name + Constants.DATAPACK_SUFFIX

        #used to format setup_load.mcfunction
        #passing 'locals()' to subfunctions makes it possible to format the template
        #  strings without explicitly passing every variable
        dp_version_str = f'v{self._version_major}.{self._version_minor}'

        #capture base dir
        base_dir = os.getcwd()

        #write datapack
        #use chdir to move around directory structure and reduce file paths
        try:
            self.write_dp_framework(entry_list, datapack_name, pack_format)

            os.chdir(os.path.join(base_dir, datapack_name, 'data', 'minecraft', 'tags', 'functions'))
            self.write_func_tags(datapack_name)

            os.chdir(os.path.join(base_dir, datapack_name, 'data', datapack_name, 'advancements'))
            self.write_advancements(datapack_name)


            os.chdir(base_dir)
            self.write_global_funcs(datapack_name, dp_version_str)
            self.write_funcs_to_register_jukebox(datapack_name)
            self.write_jukebox_tick_funcs(datapack_name)
            self.write_player_tick_funcs(base_dir, datapack_name, locals())
            self.write_per_disc_funcs(entry_list, base_dir, datapack_name, offset, locals())


            os.chdir(os.path.join(base_dir, datapack_name, 'data', datapack_name, 'functions'))
            self.write_funcs_entry_per_disc(entry_list, datapack_name, pack_format, offset)

            os.chdir(os.path.join(base_dir, datapack_name, 'data', 'minecraft', 'loot_tables', 'entities'))
            self.write_creeper_loottable(entry_list, pack_format, offset)

        except UnicodeEncodeError:
            return Status.BAD_UNICODE_CHAR

        finally:
            os.chdir(base_dir)

        #copy pack.png
        try:
            if 'pack' in user_settings:
                shutil.copyfile(user_settings['pack'], os.path.join(datapack_name, 'pack.png'))
            else:
                raise FileNotFoundError

        except (FileNotFoundError, IOError):
            print("Warning: No pack.png found. Your datapack will not have an icon.")

        #move pack to .zip, if selected
        use_zip = user_settings.get('zip', False)

        if use_zip:
            zip_status = self.zip_pack(datapack_name)

            if(zip_status != Status.SUCCESS):
                print("Error: Failed to zip datapack. Datapack has been generated as folder instead.")
                return zip_status

        return Status.SUCCESS

    # generate directory structure and framework files
    #TODO: move inside dp immediately so there's no risk of breaking external stuff
    #TODO: don't delete if mcmeta is not inside datapack_name
    def write_dp_framework(self, entry_list: DiscListContents, datapack_name: str, pack_format: int):

        #build datapack directory tree
        shutil.rmtree(datapack_name, ignore_errors=True)
        os.makedirs(os.path.join(datapack_name, 'data', 'minecraft', 'tags', 'functions'))
        os.makedirs(os.path.join(datapack_name, 'data', 'minecraft', 'loot_tables', 'entities'))
        os.makedirs(os.path.join(datapack_name, 'data', datapack_name, 'functions'))
        os.makedirs(os.path.join(datapack_name, 'data', datapack_name, 'advancements'))

        #write 'pack.mcmeta'
        with open(os.path.join(datapack_name, 'pack.mcmeta'), 'w', encoding='utf-8') as pack:
            pack.write(json.dumps({
                'pack': {
                    'pack_format': pack_format,
                    'description': (Constants.DATAPACK_DESC % len(entry_list.internal_names))
                }
            }, indent=4))

    # generate minecraft function tags
    def write_func_tags(self, datapack_name: str):

        #write 'load.json'
        with open('load.json', 'w', encoding='utf-8') as load:
            load.write(json.dumps({
                'values':[ f'{datapack_name}:setup_load' ]
            }, indent=4))

        #write 'tick.json'
        with open('tick.json', 'w', encoding='utf-8') as tick:
            tick.write(json.dumps({
                'values':[
                    f'{datapack_name}:register_players_tick',
                    f'{datapack_name}:jukebox_event_tick'
                ]
            }, indent=4))

    # generate advancements
    def write_advancements(self, datapack_name: str):

        #write 'placed_disc.json'
        with open('placed_disc.json', 'w', encoding='utf-8') as placed_disc:
            placed_disc.write(json.dumps({
                'criteria':{
                    'placed_music_disc':{
                        'trigger':'minecraft:item_used_on_block',
                        'conditions':{
                            'location':{
                                'block':{
                                    'blocks':[ 'minecraft:jukebox' ],
                                    'state':{ 'has_record':'true' }
                                }
                            },
                            'item':{'tag': 'minecraft:music_discs'}
                        }
                    }
                },
                'rewards':{
                    'function':f'{datapack_name}:on_placed_disc'
                }
            }, indent=4))

        #write 'placed_jukebox.json'
        with open('placed_jukebox.json', 'w', encoding='utf-8') as placed_jukebox:
            placed_jukebox.write(json.dumps({
                'criteria':{
                    'placed_jukebox':{
                        'trigger':'minecraft:placed_block',
                        'conditions':{
                            'block':'minecraft:jukebox',
                            'item':{
                                'items':[ 'minecraft:jukebox' ]
                            }
                        }
                    }
                },
                'rewards':{
                    'function':f'{datapack_name}:on_placed_jukebox'
                }
            }, indent=4))

    # generate global functions
    def write_global_funcs(self, datapack_name: str, dp_version_str: str):

        ref_base = os.path.abspath(Helpers.data_path())
        dst_base = os.getcwd()

        ref_dir = os.path.join(ref_base, 'reference', 'data', 'reference', 'functions')
        dst_dir = os.path.join(dst_base, datapack_name, 'data', datapack_name, 'functions')

        #write 'setup_load.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'setup_load.mcfunction'),
                           os.path.join(dst_dir, 'setup_load.mcfunction'),
                           locals())

        #write 'watchdog_reset_tickcount.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'watchdog_reset_tickcount.mcfunction'),
                           os.path.join(dst_dir, 'watchdog_reset_tickcount.mcfunction'),
                           locals())

        #write 'help.mcfunction'
        #users can run help function to see an FAQ + links to help resources
        self.copy_with_fmt(os.path.join(ref_dir, 'help.mcfunction'),
                           os.path.join(dst_dir, 'help.mcfunction'),
                           locals())

    # generate 'jukebox registration' functions
    # every jukebox must be registered with the datapack to detect
    #    discs inserted/removed with hoppers
    def write_funcs_to_register_jukebox(self, datapack_name: str):

        ref_base = os.path.abspath(Helpers.data_path())
        dst_base = os.getcwd()

        ref_dir = os.path.join(ref_base, 'reference', 'data', 'reference', 'functions')
        dst_dir = os.path.join(dst_base, datapack_name, 'data', datapack_name, 'functions')

        #write 'on_placed_disc.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'on_placed_disc.mcfunction'),
                           os.path.join(dst_dir, 'on_placed_disc.mcfunction'),
                           locals())

        #write 'on_placed_jukebox.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'on_placed_jukebox.mcfunction'),
                           os.path.join(dst_dir, 'on_placed_jukebox.mcfunction'),
                           locals())

        #write 'raycast_start.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'raycast_start.mcfunction'),
                           os.path.join(dst_dir, 'raycast_start.mcfunction'),
                           locals())

        #write 'raycast_step.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'raycast_step.mcfunction'),
                           os.path.join(dst_dir, 'raycast_step.mcfunction'),
                           locals())

        #write 'raycast_hit.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'raycast_hit.mcfunction'),
                           os.path.join(dst_dir, 'raycast_hit.mcfunction'),
                           locals())

        #write 'register_jukebox_marker.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'register_jukebox_marker.mcfunction'),
                           os.path.join(dst_dir, 'register_jukebox_marker.mcfunction'),
                           locals())

    # generate jukebox related every-tick functions
    # not all functions run every tick; some are simply called by
    #    functions that run every tick
    def write_jukebox_tick_funcs(self, datapack_name: str):

        ref_base = os.path.abspath(Helpers.data_path())
        dst_base = os.getcwd()

        ref_dir = os.path.join(ref_base, 'reference', 'data', 'reference', 'functions')
        dst_dir = os.path.join(dst_base, datapack_name, 'data', datapack_name, 'functions')

        #write 'jukebox_event_tick.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'jukebox_event_tick.mcfunction'),
                           os.path.join(dst_dir, 'jukebox_event_tick.mcfunction'),
                           locals())

        #write 'destroy_jukebox_marker.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'destroy_jukebox_marker.mcfunction'),
                           os.path.join(dst_dir, 'destroy_jukebox_marker.mcfunction'),
                           locals())

        #write 'jukebox_tick_timers.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'jukebox_tick_timers.mcfunction'),
                           os.path.join(dst_dir, 'jukebox_tick_timers.mcfunction'),
                           locals())

        #TODO: in multiplayer is marker tagged multiple times, once per player?
        #write 'stop_11.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'stop_11.mcfunction'),
                           os.path.join(dst_dir, 'stop_11.mcfunction'),
                           locals())

        #write 'jukebox_check_playing.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'jukebox_check_playing.mcfunction'),
                           os.path.join(dst_dir, 'jukebox_check_playing.mcfunction'),
                           locals())

        #TODO: technically should check if custommodeldata is within acceptable range
        #write 'jukebox_on_play.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'jukebox_on_play.mcfunction'),
                           os.path.join(dst_dir, 'jukebox_on_play.mcfunction'),
                           locals())

        #write 'pre_play.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'pre_play.mcfunction'),
                           os.path.join(dst_dir, 'pre_play.mcfunction'),
                           locals())

        #write 'register_jukebox_listener.mcfunction'
        #TODO: 2 lists is sloppy, try to optimize
        self.copy_with_fmt(os.path.join(ref_dir, 'register_jukebox_listener.mcfunction'),
                           os.path.join(dst_dir, 'register_jukebox_listener.mcfunction'),
                           locals())

        #write 'jukebox_on_stop.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'jukebox_on_stop.mcfunction'),
                           os.path.join(dst_dir, 'jukebox_on_stop.mcfunction'),
                           locals())

    # generate player related every-tick functions
    def write_player_tick_funcs(self, datapack_name: str):

        ref_base = os.path.abspath(Helpers.data_path())
        dst_base = os.getcwd()

        ref_dir = os.path.join(ref_base, 'reference', 'data', 'reference', 'functions')
        dst_dir = os.path.join(dst_base, datapack_name, 'data', datapack_name, 'functions')

        #write 'register_players_tick.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'register_players_tick.mcfunction'),
                           os.path.join(dst_dir, 'register_players_tick.mcfunction'),
                           locals())

        #TODO: different global id per-datapack?
        #write 'register_player.mcfunction'
        self.copy_with_fmt(os.path.join(ref_dir, 'register_player.mcfunction'),
                           os.path.join(dst_dir, 'register_player.mcfunction'),
                           locals())

    # generate files with lines for every disc
    # used to select which disc-specific function to run
    def write_funcs_entry_per_disc(self, entry_list: DiscListContents, datapack_name: str, pack_format: int, offset: int):

        #write 'play.mcfunction'
        with open('play.mcfunction', 'w', encoding='utf-8') as play:
            for i, name in enumerate(entry_list.internal_names):
                j = i + offset + 1

                play.write(f'execute if score @e[type=marker,tag=imd_jukebox_marker,distance=..0.1,limit=1] imd_disc_id matches {j} run function {datapack_name}:{name}/play\n')

        #write 'play_duration.mcfunction'
        with open('play_duration.mcfunction', 'w', encoding='utf-8') as play_duration:
            for i, name in enumerate(entry_list.internal_names):
                j = i + offset + 1

                play_duration.write(f'execute if score @s imd_disc_id matches {j} run function {datapack_name}:{name}/play_duration\n')

        #write 'stop.mcfunction'
        with open('stop.mcfunction', 'w', encoding='utf-8') as stop:
            for i, name in enumerate(entry_list.internal_names):
                j = i + offset + 1

                stop.write(f'execute if score @s imd_disc_id matches {j} run function {datapack_name}:{name}/stop\n')

        #write 'set_disc_track.mcfunction'
        with open('set_disc_track.mcfunction', 'w', encoding='utf-8') as set_disc_track:
            for i, track in enumerate(entry_list.titles):
                j = i + offset + 1

                # Create command, and add command as string to the rest of the command.
                item_cmd = ReplaceItemCommand(target_entity="@s", slot=ItemSlot.WEAPON_MAINHAND, item="minecraft:music_disc_11{CustomModelData:%d, HideFlags:32, display:{Lore:[\"\\\"\\\\u00a77%s\\\"\"]}}")
                cmd_str = 'execute as @s[nbt={SelectedItem:{id:"minecraft:music_disc_11", tag:{CustomModelData:%d}}}] run ' + item_cmd.command_by_pack_format(pack_format) + '\n'

                set_disc_track.write(cmd_str % (j, j, track))

        #write 'give_all_discs.mcfunction'
        with open('give_all_discs.mcfunction', 'w', encoding='utf-8') as give_all:
            for i, name in enumerate(entry_list.internal_names):
                j = i + offset + 1

                give_all.write(f'execute at @s run function {datapack_name}:give_{name}\n')

    # generate creeper loottable
    def write_creeper_loottable(self, entry_list: DiscListContents, pack_format: int, offset: int):

        #write 'creeper.json'
        with open(os.path.join('creeper.json'), 'w', encoding='utf-8') as creeper:

            discs_tag = 'minecraft:creeper_drop_music_discs'
            if pack_format < 6:
                discs_tag = 'minecraft:music_discs'

            creeper_mdentries = []
            creeper_mdentries.append({'type':'minecraft:tag', 'weight':1, 'name':discs_tag, 'expand':True})
            for i, track in enumerate(entry_list.titles):
                j = i + offset + 1

                creeper_mdentries.append({
                    'type':'minecraft:item',
                    'weight':1,
                    'name':'minecraft:music_disc_11',
                    'functions':[{
                        'function':'minecraft:set_nbt',
                        'tag':'{CustomModelData:%d, HideFlags:32, display:{Lore:[\"\\\"\\\\u00a77%s\\\"\"]}}' % (j, track)
                    }]
                })

            creeper_normentries = [{
                'type':'minecraft:item',
                'functions':[{
                        'function':'minecraft:set_count',
                        'count':{'min':0.0, 'max':2.0, 'type':'minecraft:uniform'}
                    }, {
                        'function':'minecraft:looting_enchant',
                        'count':{'min':0.0, 'max':1.0}
                    }],
                'name':'minecraft:gunpowder'
            }]

            creeper.write(json.dumps({
                'type':'minecraft:entity',
                'pools':[
                    {'rolls':1, 'entries':creeper_normentries},
                    {'rolls':1, 'entries':creeper_mdentries, 'conditions':[{
                        'condition':'minecraft:entity_properties',
                        'predicate':{'type':'#minecraft:skeletons'},
                        'entity':'killer'
                    }]
                }]
            }, indent=4))

    # generate per-disc functions
    # each disc gets a copy of these functions
    def write_per_disc_funcs(self, entry_list: DiscListContents, base_dir: str, datapack_name: str, offset: int, locals_dict: dict):

        ref_base = os.path.abspath(Helpers.data_path())

        ref_dir = os.path.join(ref_base, 'reference', 'data', 'reference', 'functions')
        dst_dir = os.path.join(base_dir, datapack_name, 'data', datapack_name, 'functions')

        for i, entry in enumerate(entry_list.entries):
            #make directory for this disc's functions
            os.makedirs(os.path.join(dst_dir, entry.internal_name))

            #write '*/play.mcfunction' files
            self.copy_with_fmt(os.path.join(ref_dir, 'disc', 'play.mcfunction'),
                               os.path.join(dst_dir, entry.internal_name, 'play.mcfunction'),
                               {**locals_dict, **locals()})

            #write '*/play_duration.mcfunction' files
            self.copy_with_fmt(os.path.join(ref_dir, 'disc', 'play_duration.mcfunction'),
                               os.path.join(dst_dir, entry.internal_name, 'play_duration.mcfunction'),
                               {**locals_dict, **locals()})

            #write '*/stop.mcfunction' files
            self.copy_with_fmt(os.path.join(ref_dir, 'disc', 'stop.mcfunction'),
                               os.path.join(dst_dir, entry.internal_name, 'stop.mcfunction'),
                               {**locals_dict, **locals()})

            #write 'give_*_disc.mcfunction' files
            j = i + offset + 1

            with open(os.path.join(dst_dir, f'give_{entry.internal_name}.mcfunction'), 'w', encoding='utf-8') as give:
                give.write('execute at @s run summon item ~ ~ ~ {Item:{id:"minecraft:music_disc_11", Count:1b, tag:{CustomModelData:%d, HideFlags:32, display:{Lore:[\"\\\"\\\\u00a77%s\\\"\"]}}}}\n' % (j, entry.title))



    def generate_resourcepack(self, entry_list: DiscListContents, user_settings={}, cleanup_tmp: bool = True):

        #read settings
        pack_format = user_settings.get('version').get('rp', Constants.DEFAULT_PACK_FORMAT)
        offset = user_settings.get('offset', 0)

        resourcepack_name = user_settings.get('name', Constants.DEFAULT_PACK_NAME)
        resourcepack_name = resourcepack_name + Constants.RESOURCEPACK_SUFFIX

        #capture base dir
        base_dir = os.getcwd()

        #write resourcepack
        #use chdir to move around directory structure and reduce file paths
        try:
            self.write_rp_framework(entry_list, resourcepack_name, pack_format)

            os.chdir(os.path.join(base_dir, resourcepack_name, 'assets', 'minecraft', 'models', 'item'))
            self.write_item_models(entry_list, offset)

            os.chdir(os.path.join(base_dir, resourcepack_name, 'assets', 'minecraft'))
            self.copy_assets(entry_list)

        except UnicodeEncodeError:
            return Status.BAD_UNICODE_CHAR
        
        finally:
            os.chdir(base_dir)

        #copy pack.png
        try:
            if 'pack' in user_settings:
                shutil.copyfile(user_settings['pack'], os.path.join(resourcepack_name, 'pack.png'))
            else:
                raise FileNotFoundError

        except (FileNotFoundError, IOError):
            print("Warning: No pack.png found. Your resourcepack will not have an icon.")

        #move pack to .zip, if selected
        use_zip = user_settings.get('zip', False)

        if use_zip:
            zip_status = self.zip_pack(resourcepack_name)

            if(zip_status != Status.SUCCESS):
                print("Error: Failed to zip resourcepack. Resourcepack has been generated as folder instead.")
                return zip_status

        #cleanup temp work directory
        if cleanup_tmp:
            shutil.rmtree(self.tmp_path, ignore_errors=True)
            self.tmp_path = None

        return Status.SUCCESS

    # generate directory structure and framework files
    def write_rp_framework(self, entry_list: DiscListContents, resourcepack_name: str, pack_format: int):

        #build resourcepack directory tree
        shutil.rmtree(resourcepack_name, ignore_errors=True)
        os.makedirs(os.path.join(resourcepack_name, 'assets', 'minecraft', 'models', 'item'))
        os.makedirs(os.path.join(resourcepack_name, 'assets', 'minecraft', 'sounds', 'records'))
        os.makedirs(os.path.join(resourcepack_name, 'assets', 'minecraft', 'textures', 'item'))

        #write 'pack.mcmeta'
        with open(os.path.join(resourcepack_name, 'pack.mcmeta'), 'w', encoding='utf-8') as pack:
            pack.write(json.dumps({
                'pack':{
                    'pack_format':pack_format,
                    'description':(Constants.RESOURCEPACK_DESC % len(entry_list.internal_names))
                }
            }, indent=4))

        #write 'sounds.json'
        with open(os.path.join(resourcepack_name, 'assets', 'minecraft', 'sounds.json'), 'w', encoding='utf-8') as sounds:
            json_dict = {}

            for name in entry_list.internal_names:
                sound = {
                    'sounds':[{
                        'name':f'records/{name}',
                        'stream':True
                    }]
                }

                json_dict[f'music_disc.{name}'] = sound

            sounds.write(json.dumps(json_dict, indent=4))

    # generate item models
    def write_item_models(self, entry_list: DiscListContents, offset: int):

        #write 'music_disc_11.json'
        with open('music_disc_11.json', 'w', encoding='utf-8') as music_disc_11:
            json_list = []
            for i, name in enumerate(entry_list.internal_names):
                j = i + offset + 1

                json_list.append({
                    'predicate':{'custom_model_data':j},
                    'model':f'item/music_disc_{name}'
                })

            music_disc_11.write(json.dumps({
                'parent':'item/generated',
                'textures':{'layer0': 'item/music_disc_11'},
                'overrides':json_list
            }, indent=4))

        #write 'music_disc_*.json' files
        for name in entry_list.internal_names:
            with open(f'music_disc_{name}.json', 'w', encoding='utf-8') as music_disc:
                music_disc.write(json.dumps({
                    'parent':'item/generated',
                    'textures':{'layer0': f'item/music_disc_{name}'}
                }, indent=4))

    # generate assets dir
    def copy_assets(self, entry_list: DiscListContents):

        #copy sound and texture files
        for entry in entry_list.entries:
            shutil.copyfile(entry.track_file, os.path.join('sounds', 'records', f'{entry.internal_name}.ogg'))
            shutil.copyfile(entry.texture_file, os.path.join('textures', 'item', f'music_disc_{entry.internal_name}.png'))



    def zip_pack(self, pack_name: str):
        pack_name_zip = pack_name + Constants.ZIP_SUFFIX

        try:
            #remove old zip
            if os.path.exists(pack_name_zip):
                os.remove(pack_name_zip)

            #generate new zip archive
            with zipfile.ZipFile(pack_name_zip, 'w') as rp_zip:
                for root, dirs, files in os.walk(pack_name):
                    root_zip = os.path.relpath(root, pack_name)

                    for file in files:
                        rp_zip.write(os.path.join(root, file), os.path.join(root_zip, file))

            #remove pack folder
            if os.path.exists(pack_name_zip):
                shutil.rmtree(pack_name, ignore_errors=True)

        except (OSError, zipfile.BadZipFile):
            #remove bad zip, if it exists
            if os.path.exists(pack_name_zip):
                os.remove(pack_name_zip)

            return Status.BAD_ZIP
        
        return Status.SUCCESS

    def copy_with_fmt(self, f_src: str, f_dst: str, fmt_dict):
        with open(f_src, 'r', encoding='utf-8') as src:
            with open(f_dst, 'w', encoding='utf-8') as dst:
                for line in src.readlines():
                    #line_fmt = line.replace('{', '{{')
                    #line_fmt = line_fmt.replace('}', '}}')
                    #line_fmt = line_fmt.replace('%(', '{')
                    #line_fmt = line_fmt.replace(')%', '}')

                    line_fmt = line.format(**fmt_dict)
                    dst.write(line_fmt)

    def copy_multi_line_with_fmt(self, f_src: str, f_dst: str, entry_list: DiscListContents, fmt_dict):
        with open(f_src, 'r', encoding='utf-8') as src:
            with open(f_dst, 'a', encoding='utf-8') as dst:
                for line in src.readlines():
                    line_fmt = line.format(**fmt_dict)
                    dst.write(line_fmt)



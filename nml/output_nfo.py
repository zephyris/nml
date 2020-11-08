__license__ = """
NML is free software; you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation; either version 2 of the License, or
(at your option) any later version.

NML is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License along
with NML; if not, write to the Free Software Foundation, Inc.,
51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA."""

# -*- coding: utf-8 -*-
import io

from nml import generic, grfstrings, output_base
from nml.actions import real_sprite

zoom_levels = {
    0: "normal",
    1: "zi4",
    2: "zi2",
    3: "zo2",
    4: "zo4",
    5: "zo8",
}

bit_depths = {
    8: "8bpp",
    32: "32bpp",
}


class OutputNFO(output_base.SpriteOutputBase):
    def __init__(self, filename, start_sprite_num):
        output_base.SpriteOutputBase.__init__(self, filename)
        self.sprite_num = start_sprite_num

    def open(self):
        self.file = io.StringIO()

    def open_file(self):
        handle = open(self.filename, "w", encoding="utf-8")
        handle.write(
            "// Automatically generated by GRFCODEC. Do not modify!\n"
            "// (Info version 32)\n"
            "// Escapes: 2+ 2- 2< 2> 2u< 2u> 2/ 2% 2u/ 2u% 2* 2& 2| 2^"
            " 2sto = 2s 2rst = 2r 2psto 2ror = 2rot 2cmp 2ucmp 2<< 2u>> 2>>\n"
            "// Escapes: 71 70 7= 7! 7< 7> 7G 7g 7gG 7GG 7gg 7c 7C\n"
            "// Escapes: D= = DR D+ = DF D- = DC Du* = DM D* = DnF Du<< = DnC D<< = DO D& D| Du/ D/ Du% D%\n"
            "// Format: spritenum imagefile depth xpos ypos xsize ysize xrel yrel zoom flags\n\n"
        )
        return handle

    def assemble_file(self, real_file):
        # All print functions add a space in case there's something written after so remove trailing whitespaces
        real_file.write(self.file.getvalue().replace(" \n", "\n"))

    def print_byte(self, value):
        value = self.prepare_byte(value)
        self.file.write("\\b" + str(value) + " ")

    def print_bytex(self, value, pretty_print=None):
        value = self.prepare_byte(value)
        if pretty_print is not None:
            self.file.write(pretty_print + " ")
            return
        self.file.write("{:02X} ".format(value))

    def print_word(self, value):
        value = self.prepare_word(value)
        self.file.write("\\w{:d} ".format(value))

    def print_wordx(self, value):
        value = self.prepare_word(value)
        self.file.write("\\wx{:04X} ".format(value))

    def print_dword(self, value):
        value = self.prepare_dword(value)
        self.file.write("\\d{:d} ".format(value))

    def print_dwordx(self, value):
        value = self.prepare_dword(value)
        self.file.write("\\dx{:08X} ".format(value))

    def print_string(self, value, final_zero=True, force_ascii=False):
        assert self.in_sprite
        self.file.write('"')
        if not grfstrings.is_ascii_string(value):
            if force_ascii:
                raise generic.ScriptError("Expected ascii string but got a unicode string")
            self.file.write("Þ")  # b'\xC3\x9E'.decode('utf-8')
        self.file.write(value.replace('"', '\\"'))
        self.byte_count += grfstrings.get_string_size(value, final_zero, force_ascii)
        self.file.write('" ')
        if final_zero:
            self.print_bytex(0)
            # get_string_size already includes the final 0 byte
            # but print_bytex also increases byte_count, so decrease
            # it here by one to correct it.
            self.byte_count -= 1

    def print_decimal(self, value):
        assert self.in_sprite
        self.file.write(str(value) + " ")

    def newline(self, msg="", prefix="\t"):
        if msg != "":
            msg = prefix + "// " + msg
        self.file.write(msg + "\n")

    def comment(self, msg):
        self.file.write("// " + msg + "\n")

    def start_sprite(self, size, is_real_sprite=False):
        output_base.SpriteOutputBase.start_sprite(self, size)
        self.print_decimal(self.sprite_num)
        self.sprite_num += 1
        if not is_real_sprite:
            self.file.write("* ")
            self.print_decimal(size)

    def print_sprite(self, sprite_list):
        """
        @param sprite_list: List of non-empty real sprites for various bit depths / zoom levels
        @type  sprite_list: C{list} of L{RealSprite}
        """
        self.start_sprite(0, True)
        for i, sprite_info in enumerate(sprite_list):
            self.file.write(sprite_info.file.value + " ")
            self.file.write(bit_depths[sprite_info.bit_depth] + " ")
            self.print_decimal(sprite_info.xpos.value)
            self.print_decimal(sprite_info.ypos.value)
            self.print_decimal(sprite_info.xsize.value)
            self.print_decimal(sprite_info.ysize.value)
            self.print_decimal(sprite_info.xrel.value)
            self.print_decimal(sprite_info.yrel.value)
            self.file.write(zoom_levels[sprite_info.zoom_level] + " ")
            if (sprite_info.flags.value & real_sprite.FLAG_NOCROP) != 0:
                self.file.write("nocrop ")
            if sprite_info.mask_file is not None:
                self.newline()
                self.file.write("|\t")
                self.file.write(sprite_info.mask_file.value)
                self.file.write(" mask ")
                mask_x, mask_y = (
                    sprite_info.mask_pos if sprite_info.mask_pos is not None else (sprite_info.xpos, sprite_info.ypos)
                )
                self.print_decimal(mask_x.value)
                self.print_decimal(mask_y.value)
            if i + 1 < len(sprite_list):
                self.newline()
                self.file.write("|\t")
        self.end_sprite()

    def print_empty_realsprite(self):
        self.start_sprite(1)
        self.print_bytex(0)
        self.end_sprite()

    def print_named_filedata(self, filename):
        self.start_sprite(0, True)
        self.file.write("** " + filename)
        self.end_sprite()

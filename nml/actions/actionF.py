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

"""
Code for storing and generating action F
"""
from nml import expression, generic, grfstrings
from nml.actions import base_action

# Helper functions to allocate townname IDs
#
# Numbers available are from 0 to 0x7f (inclusive).
# These numbers can be in five states:
# - free:            Number is available for use.
# - named:           Number is allocated to represent a name.
# - safe numbered:   Number is allocated by the user, and is safe to refer to.
# - unsafe numbered: Number is allocated by the user, and is not safe to refer to
#                    (that is, it is below the point of 'prepare_output')
# - invisible:       Number is allocated by a final town_name, without attaching a name to it.
#                    It is not accessible any more.
# Instances of the TownNames class have a 'name' attribute, which can be 'None' (for an invisible number),
# a string (for a named number), or a (constant numeric) expression (for a safe/unsafe number).
#
total_numbers = 0x80
free_numbers = set(range(total_numbers))  #: Free numbers.
first_free_id = 0  #: All numbers before this are allocated.
named_numbers = {}  #: Mapping of names to named numbers. Note that these are always safe to refer to.
numbered_numbers = set()  #: Safe numbers introduced by the user (without name).


def get_free_id():
    """Allocate a number from the free_numbers."""
    global first_free_id
    while first_free_id not in free_numbers:
        first_free_id = first_free_id + 1
        if first_free_id >= total_numbers:
            raise generic.ScriptError(
                "Too many town name blocks. Some of these are autogenerated. Please use less town names."
            )
    number = first_free_id
    free_numbers.remove(number)
    first_free_id = first_free_id + 1
    return number


town_names_blocks = {}  # Mapping of town_names ID number to TownNames instance.


def print_stats():
    """
    Print statistics about used ids.
    """
    num_used = total_numbers - len(free_numbers)
    if num_used > 0:
        generic.print_info("Town names: {}/{}".format(num_used, total_numbers))


class ActionF(base_action.BaseAction):
    """
    Town names action.

    @ivar name: Name ID of the town_name.
    @type name: C{None}, L{Identifier}, or L{ConstantNumeric}

    @ivar id_number: Allocated ID number for this town_name action F node.
    @type id_number: C{None} or C{int}

    @ivar style_name: Name of the translated string containing the name of the style, if any.
    @type style_name: C{None} or L{String}

    @ivar style_names: List translations of L{style_name}, pairs (languageID, text).
    @type style_names: C{list} of (C{int}, L{Identifier})

    @ivar parts: Parts of the names.
    @type parts: C{list} of L{TownNamesPart}

    @ivar free_bit: First available bit above the bits used by this block.
    @type free_bit: C{None} if unset, else C{int}

    @ivar pos: Position information of the 'town_names' block.
    @type pos: L{Position}
    """

    def __init__(self, name, id_number, style_name, parts, pos):
        self.name = name
        self.id_number = id_number
        self.style_name = style_name
        self.style_names = []
        self.parts = parts
        self.free_bit = None
        self.pos = pos

    def prepare_output(self, sprite_num):
        # Resolve references to earlier townname actions
        blocks = set()
        for part in self.parts:
            blocks.update(part.resolve_townname_id())

        # Allocate a number for this action F.
        if self.name is None or isinstance(self.name, expression.Identifier):
            self.id_number = get_free_id()
            if isinstance(self.name, expression.Identifier):
                if self.name.value in named_numbers:
                    raise generic.ScriptError(
                        'Cannot define town name "{}", it is already in use'.format(self.name), self.pos
                    )
                named_numbers[self.name.value] = self.id_number  # Add name to the set 'safe' names.
        else:
            numbered_numbers.add(self.id_number)  # Add number to the set of 'safe' numbers.

        # Ask existing action F for the lowest available bit.
        if len(town_names_blocks) == 0:
            startbit = 0
        else:
            startbit = max(block.free_bit for block in town_names_blocks.values())

        town_names_blocks[self.id_number] = self  # Add self to the available blocks.

        # Allocate random bits to all parts.
        for part in self.parts:
            num_bits = part.assign_bits(startbit)
            # Prevent overlap if really needed
            if len(part.pieces) > 1:
                startbit += num_bits
        self.free_bit = startbit

        if startbit > 32:
            raise generic.ScriptError(
                "Not enough random bits for the town name generation ({:d} needed, 32 available)".format(startbit),
                self.pos,
            )

        # Pull style names if needed.
        if self.style_name is not None:
            grfstrings.validate_string(self.style_name)
            self.style_names = [
                (lang_id, grfstrings.get_translation(self.style_name, lang_id))
                for lang_id in grfstrings.get_translations(self.style_name)
            ]
            self.style_names.append((0x7F, grfstrings.get_translation(self.style_name)))
            self.style_names.sort()
            if len(self.style_names) == 0:
                raise generic.ScriptError(
                    'Style "{}" defined, but no translations found for it'.format(self.style_name.name.value), self.pos
                )
        else:
            self.style_names = []

    # Style names
    def get_length_styles(self):
        if len(self.style_names) == 0:
            return 0

        size = 0
        for _lang, txt in self.style_names:
            size += 1 + grfstrings.get_string_size(txt)  # Language ID, text
        return size + 1  # Terminating 0

    def write_styles(self, handle):
        if len(self.style_names) == 0:
            return

        for lang, txt in self.style_names:
            handle.print_bytex(lang)
            handle.print_string(txt, final_zero=True)
            handle.newline()
        handle.print_bytex(0)
        handle.newline()

    # Parts
    def get_length_parts(self):
        size = 1  # num_parts byte
        return size + sum(part.get_length() for part in self.parts)

    def write_parts(self, handle):
        handle.print_bytex(len(self.parts))
        for part in self.parts:
            part.write(handle)
            handle.newline()

    def write(self, handle):
        handle.start_sprite(2 + self.get_length_styles() + self.get_length_parts())
        handle.print_bytex(0xF)
        handle.print_bytex(self.id_number | (0x80 if len(self.style_names) > 0 else 0))
        handle.newline(str(self.name) if self.name is not None else "")
        self.write_styles(handle)
        self.write_parts(handle)
        handle.end_sprite()

    def skip_action7(self):
        return False

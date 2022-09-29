# Copyright (c) OpenMMLab. All rights reserved.
import copy
from typing import Dict, List, Tuple, Union

# Channels


class BaseChannel:
    """BaseChannel records information about channels for pruning.

    Args:
        name (str): The name of the channel. When the channel is related with
            a module, the name should be the name of the module in the model.
        module (Any): Module of the channel.
        index (Tuple[int,int]): Index(start,end) of the Channel in the Module
        node (ChannelNode, optional): A ChannelNode corresponding to the
            Channel. Defaults to None.
        is_output_channel (bool, optional): Is the channel output channel.
            Defaults to True.
        expand_ratio (int, optional): Expand ratio of the mask. Defaults to 1.
    """

    # init

    def __init__(self,
                 name,
                 module,
                 index,
                 node=None,
                 is_output_channel=True,
                 expand_ratio=1) -> None:
        self.name = name
        self.module = module
        self.index = index
        self.start = index[0]
        self.end = index[1]

        self.node = node

        self.is_output_channel = is_output_channel
        self.expand_ratio = expand_ratio

    @property
    def num_channels(self) -> int:
        """The number of channels in the Channels."""
        return self.index[1] - self.index[0]

    # others

    def __repr__(self) -> str:
        return f'{self.name}\t{self.index}\t \
        {"out" if self.is_output_channel else "in"}\t\
        expand:{self.expand_ratio}'

    def __eq__(self, obj: object) -> bool:
        if isinstance(obj, BaseChannel):
            return self.name == obj.name \
                and self.module == obj.module \
                and self.index == obj.index \
                and self.is_output_channel == obj.is_output_channel \
                and self.expand_ratio == obj.expand_ratio \
                and self.node == obj.node
        else:
            return False


class BaseChannelGroup:
    """BaseChannelGroup is a collection of BaseChannel.

    All  BaseChannels are saved in two lists: self.input_related and
    self.output_related.
    """

    def __init__(self) -> None:

        self.channel_elems: Dict[int, List[ChannelElement]] = {}
        self.input_related: List[BaseChannel] = []
        self.output_related: List[BaseChannel] = []

    # ~

    def add_channel_elem(self, channel_elem: 'ChannelElement', index):
        """Add a ChannelElement to the BaseChannelGroup."""
        self._add_channel_info(channel_elem, index)
        if channel_elem.group is not None:
            channel_elem.remove_from_group()
        channel_elem._register_group(self, index)

    # group operations

    @classmethod
    def union_groups(cls, groups: List['BaseChannelGroup']):
        """Union groups."""
        assert len(groups) > 1
        union_group = groups[0]

        for group in groups[1:]:
            union_group = BaseChannelGroup.union_two_groups(union_group, group)
        return union_group

    @classmethod
    def union_two_groups(cls, group1: 'BaseChannelGroup',
                         group2: 'BaseChannelGroup'):
        """Union two groups."""
        if group1 is group2:
            return group1
        else:
            assert len(group1) == len(group2)
            for i in group1:
                for channel_elem in copy.copy(group2[i]):
                    group1.add_channel_elem(channel_elem, i)
            return group1

    @classmethod
    def split_group(cls, group: 'BaseChannelGroup', nums: List[int]):
        """Split a group to multiple groups."""
        new_groups = []
        if len(nums) == 1:
            return [group]
        assert sum(nums) == len(group)
        for num in nums:
            new_group = group._split_a_new_group(list(range(0, num)))
            new_groups.append(new_group)
        return new_groups

    # private methods

    def _clean_channel_info(self, channel_elem: 'ChannelElement', index: int):
        """Clean the info of a ChannelElement."""
        self[index].remove(channel_elem)

    def _add_channel_info(self, channel_elem: 'ChannelElement', index):
        """Add the info of a ChannelElemnt."""
        assert channel_elem.group is not self
        if index not in self.channel_elems:
            self.channel_elems[index] = []
        self.channel_elems[index].append(channel_elem)

    def _split_a_new_group(self, indexes: List[int]):
        """Split a part of the group to a new group."""
        new_group = BaseChannelGroup()
        j = 0
        for i in indexes:
            for channel_elem in copy.copy(self[i]):
                new_group.add_channel_elem(channel_elem, j)
            self.channel_elems.pop(i)
            j += 1
        self._reindex()
        return new_group

    def _reindex(self):
        """Re-index the owning ChannelElements."""
        j = 0
        for i in copy.copy(self.channel_elems):
            if len(self.channel_elems[i]) == 0:
                self.channel_elems.pop(i)
            else:
                if j < i:
                    for channel_elem in copy.copy(self.channel_elems[i]):
                        if channel_elem.group is not None:
                            channel_elem.remove_from_group()
                        self.add_channel_elem(channel_elem, j)
                    self.channel_elems.pop(i)
                    j += 1
                elif j == i:
                    pass
                else:
                    raise Exception()

    # others

    def __repr__(self) -> str:

        def add_prefix(string: str, prefix='  '):
            str_list = string.split('\n')
            str_list = [
                prefix + line if line != '' else line for line in str_list
            ]
            return '\n'.join(str_list)

        def list_repr(lit: List):
            s = '[\n'
            for item in lit:
                s += add_prefix(item.__repr__(), '  ') + '\n'
            s += ']\n'
            return s

        s = ('xxxxx_'
             f'\t{len(self.output_related)},{len(self.input_related)}\n')
        s += '  output_related:\n'
        s += add_prefix(list_repr(self.output_related), ' ' * 4)
        s += '  input_related\n'
        s += add_prefix(list_repr(self.input_related), ' ' * 4)
        return s

    def __iter__(self):
        for i in self.channel_elems:
            yield i

    def __len__(self):
        return len(self.channel_elems)

    def __getitem__(self, key):
        return self.channel_elems[key]


class ChannelElement:
    """Each ChannelElement is the basic element of  a ChannelTensor. It records
    its owing ChannelTensor and BaseChannelGroup.

    Args:
        index (int): The index of the ChannelElement in the ChannelTensor.
    """

    def __init__(self, index_in_tensor: int) -> None:

        self.index_in_channel_tensor = index_in_tensor

        self.group: Union[BaseChannelGroup, None] = None
        self.index_in_group = -1

    def remove_from_group(self):
        """Remove the ChannelElement from its owning BaseChannelGroup."""
        self.group._clean_channel_info(self, self.index_in_group)
        self._clean_group_info()

    # private methods

    def _register_group(self, group, index):
        """Register the ChannelElement to a BaseChannelGroup."""
        self.group = group
        self.index_in_group = index

    def _clean_group_info(self):
        """Clean the group info in the ChannelElement."""
        self.group = None
        self.index_in_group = -1


class ChannelTensor:
    """A ChannelTensor is a list of ChannelElemnts. It can forward through a
    ChannelGraph.

    Args:
        num_channel_elems (int): Number of ChannelElements.
    """

    def __init__(self, num_channel_elems: int) -> None:

        group = BaseChannelGroup()
        self.channel_elems: List[ChannelElement] = [
            ChannelElement(i) for i in range(num_channel_elems)
        ]
        for channel_elem in self.channel_elems:
            group.add_channel_elem(channel_elem,
                                   channel_elem.index_in_channel_tensor)

    # group operations

    def align_groups_with_nums(self, nums: List[int]):
        """Align owning groups to certain lengths."""
        i = 0
        for start, end in self.group_dict:
            start_ = start
            new_nums = []
            while start_ < end:
                new_nums.append(nums[i])
                start_ += nums[i]
                i += 1
            BaseChannelGroup.split_group(self.group_dict[(start, end)],
                                         new_nums)

    @property
    def group_dict(self) -> Dict[Tuple[int, int], BaseChannelGroup]:
        """Get a dict of owning groups."""
        groups: Dict[Tuple[int, int], BaseChannelGroup] = {}
        # current_group = ...
        current_group_idx = -1
        start = 0
        for i in range(len(self)):
            if i == 0:
                current_group = self[i].group
                current_group_idx = self[i].index_in_group
                start = 0
            else:
                if current_group is not self[i].group or \
                        current_group_idx > self[i].index_in_group:
                    groups[(start, i)] = current_group
                    current_group = self[i].group
                    current_group_idx = self[i].index_in_group
                    start = i
            current_group_idx = self[i].index_in_group
        groups[(start, len(self))] = current_group
        return groups

    @property
    def group_list(self) -> List[BaseChannelGroup]:
        """Get a list of owning groups."""
        return list(self.group_dict.values())

    # tensor operations

    @classmethod
    def align_tensors(cls, *tensors: 'ChannelTensor'):
        """Align the lengths of the groups of the tensors."""
        assert len(tensors) >= 2
        for tensor in tensors:
            assert len(tensor) == len(
                tensors[0]), f'{len(tensor)}!={len(tensors[0])}'
        aligned_index = cls._index2points(
            *[list(tenser.group_dict.keys()) for tenser in tensors])
        nums = cls._points2num(aligned_index)
        if len(nums) > 1:
            for tensor in tensors:
                tensor.align_groups_with_nums(nums)

    def union(self, tensor1: 'ChannelTensor'):
        """Union the groups with the tensor1."""
        # align
        ChannelTensor.align_tensors(self, tensor1)
        # union
        for ch1, ch2 in zip(self.channel_elems, tensor1.channel_elems):
            assert ch1.group is not None and ch2.group is not None
            for ch in copy.copy(ch2.group.channel_elems[ch2.index_in_group]):
                ch1.group.add_channel_elem(ch, ch1.index_in_group)

    def expand(self, ratio) -> 'ChannelTensor':
        """Get a new ChannelTensor which is expanded from this
        ChannelTensor."""
        expanded_tensor = ChannelTensor(len(self) * ratio)
        for i, ch in enumerate(self.channel_elems):
            assert ch.group is not None
            group = ch.group
            for j in range(0, ratio):
                ex_ch = expanded_tensor[i * ratio + j]
                group.add_channel_elem(ex_ch, ch.index_in_group)
        return expanded_tensor

    # others

    def __getitem__(self, i: int):
        """Get ith ChannelElement in the ChannelTensor."""
        return self.channel_elems[i]

    def __len__(self):
        """Get length of the ChannelTensor."""
        return len(self.channel_elems)

    @classmethod
    def _index2points(cls, *indexes: List[Tuple[int, int]]):
        """Convert indexes to points."""
        new_index = []
        for index in indexes:
            new_index.extend(index)
        points = set()
        for start, end in new_index:
            points.add(start)
            points.add(end)
        points_list = list(points)
        points_list.sort()
        return points_list

    @classmethod
    def _points2num(cls, indexes: List[int]):
        """Convert a list of sorted points to the length of each block."""
        if len(indexes) == 0:
            return []
        nums = []
        start = 0
        for end in indexes[1:]:
            nums.append(end - start)
            start = end
        return nums
# Copyright (c) OpenMMLab. All rights reserved.
"""This module defines MutableChannelGroup with related modules."""
import abc
import copy
from typing import Dict, Type, TypeVar, Union

import torch.nn as nn

from ....architectures.dynamic_op.bricks import (DynamicBatchNorm2d,
                                                 DynamicConv2d, DynamicLinear)
from ....architectures.dynamic_op.bricks.dynamic_mixins import \
    DynamicChannelMixin
from ...base_mutable import BaseMutable
from ..mutable_channel_container import MutableChannelContainer
from ..simple_mutable_channel import SimpleMutableChannel
from .channel_group import ChannelGroup, is_dynamic_op


class MutableChannelGroup(ChannelGroup, BaseMutable):

    def __init__(self, num_channels) -> None:
        super().__init__(num_channels)
        ChannelGroup.__init__(self, num_channels)
        BaseMutable.__init__(self)

    # basic property

    @property
    def name(self):
        """str: name of the group"""
        first_module = self.output_related[0] if len(
            self.output_related) > 0 else self.input_related[0]
        name = f'{first_module.name}_{first_module.index}_'
        name += f'_out_{len(self.output_related)}_in_{len(self.input_related)}'

        return name

    @property
    def is_prunable(self):
        """bool: if the channel-group is prunable"""
        have_dynamic_op = False
        all_node_prunable = True
        for channel in self.input_related + self.output_related:
            if channel.node.is_prunable is False:
                all_node_prunable = False
            if is_dynamic_op(channel.module):
                have_dynamic_op = True
        return len(self.output_related) > 0\
            and len(self.input_related) > 0 \
            and have_dynamic_op \
            and all_node_prunable

    # choice-related

    @property
    def current_choice(self):
        raise NotImplementedError()

    @current_choice.setter
    def current_choice(self, choice) -> None:
        """Current choice setter will be executed in mutator."""
        raise NotImplementedError()

    @abc.abstractmethod
    def sample_choice(self):
        raise NotImplementedError()

    # prepare model

    @abc.abstractclassmethod
    def prepare_model(cls, model: nn.Module):
        """Replace modules with dynamic-ops."""
        raise NotImplementedError()

    @abc.abstractmethod
    def prepare_for_pruning(self):
        """Post process after parse groups.

        For example, we need to register mutable to dynamic-ops
        """
        raise NotImplementedError()

    # tools

    def _get_int_choice(self, choice: Union[int, float]) -> int:
        if isinstance(choice, float):
            choice = max(1, int(self.num_channels * choice))
        assert 0 < choice <= self.num_channels, f'{choice}'
        return choice

    @staticmethod
    def _replace_with_dynamic_ops(
            model: nn.Module, dynamicop_map: Dict[Type[nn.Module],
                                                  Type[DynamicChannelMixin]]):
        """Replace modules with dynamic-ops."""

        def traverse(module):
            for name, child in copy.copy(list(module.named_children())):
                replaced = False
                if type(child) in dynamicop_map:
                    new_child = dynamicop_map[type(child)].convert_from(child)
                    setattr(module, name, new_child)
                    replaced = True
                if replaced is False:
                    traverse(child)

        traverse(model)
        return model

    @staticmethod
    def _register_mask_container(model: nn.Module, container_class):
        for module in model.modules():
            if isinstance(module, DynamicChannelMixin):
                if module.get_mutable_attr('in_channels') is None:
                    in_channels = 0
                    if isinstance(module, DynamicConv2d):
                        in_channels = module.in_channels
                    elif isinstance(module, DynamicBatchNorm2d):
                        in_channels = module.num_features
                    elif isinstance(module, DynamicLinear):
                        in_channels = module.in_features
                    else:
                        raise NotImplementedError()
                    module.register_mutable_attr('in_channels',
                                                 container_class(in_channels))
                if module.get_mutable_attr('out_channels') is None:
                    out_channels = 0
                    if isinstance(module, DynamicConv2d):
                        out_channels = module.out_channels
                    elif isinstance(module, DynamicBatchNorm2d):
                        out_channels = module.num_features
                    elif isinstance(module, DynamicLinear):
                        out_channels = module.out_features
                    else:
                        raise NotImplementedError()
                    module.register_mutable_attr('out_channels',
                                                 container_class(out_channels))

    def _register_mask(self, muatable_mask: SimpleMutableChannel):
        self.mutable_mask = SimpleMutableChannel(self.num_channels)

        # register MutableMask
        for channel in self.input_related + self.output_related:
            module = channel.module
            if is_dynamic_op(module):
                container: MutableChannelContainer
                if channel.output_related and module.get_mutable_attr(
                        'out_channels') is not None:
                    container = module.get_mutable_attr('out_channels')
                elif channel.output_related is False \
                        and module.get_mutable_attr('in_channels') is not None:
                    container = module.get_mutable_attr('in_channels')
                else:
                    raise NotImplementedError()

                if channel.expand_ratio == 1:
                    mutable_mask = muatable_mask
                    start = channel.start
                    end = channel.end
                else:
                    mutable_mask = muatable_mask.expand_mutable_mask(
                        channel.expand_ratio)
                    start = channel.start
                    end = channel.start + (
                        channel.end - channel.start) * channel.expand_ratio
                container.register_mutable(mutable_mask, start, end)

    # implement abstract methods

    def num_choices(self) -> int:
        return self.num_channels

    def dump_chosen(self):
        pass

    def fix_chosen(self, chosen) -> None:
        pass


MUTABLECHANNELGROUP = TypeVar('MUTABLECHANNELGROUP', bound=MutableChannelGroup)

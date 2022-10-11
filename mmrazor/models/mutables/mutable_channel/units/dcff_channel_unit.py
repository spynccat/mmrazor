# Copyright (c) OpenMMLab. All rights reserved.
from typing import List, Union

import torch.nn as nn

from mmrazor.models.architectures import dynamic_ops
from mmrazor.registry import MODELS
from ..mutable_channel_container import MutableChannelContainer
from .one_shot_mutable_channel_unit import OneShotMutableChannelUnit


@MODELS.register_module()
class DCFFChannelUnit(OneShotMutableChannelUnit):
    """``DCFFChannelUnit`` is for supernet DCFF and based on
    OneShotMutableChannelUnit. In DCFF supernet, each module only has one
    choice. The channel choice is fixed before training.

    Args:
        num_channels (int): The raw number of channels.
        candidate_choices (List[Union[int, float]], optional):
            A list of candidate width numbers or ratios. Each
            candidate indicates how many channels to be reserved.
            Defaults to [32](choice_mode='number').
        choice_mode (str, optional): Mode of candidates.
            One of "ratio" or "number". Defaults to 'number'.
    """

    def __init__(self,
                 num_channels: int,
                 candidate_choices: List[Union[int, float]] = [32],
                 choice_mode: str = 'number',
                 divisor: int = 1,
                 min_value: int = 1,
                 min_ratio: float = 0.9) -> None:
        super().__init__(num_channels, candidate_choices, choice_mode, divisor,
                         min_value, min_ratio)

    def prepare_for_pruning(self, model: nn.Module):
        """In ``DCFFChannelGroup`` nn.Conv2d is replaced with FuseConv2d."""
        self._replace_with_dynamic_ops(
            model, {
                nn.Conv2d: dynamic_ops.FuseConv2d,
                nn.BatchNorm2d: dynamic_ops.DynamicBatchNorm2d,
                nn.Linear: dynamic_ops.DynamicLinear
            })
        self._register_channel_container(model, MutableChannelContainer)
        self._register_mutable_channel(self.mutable_channel)

    def alter_candidates_after_init(self, candidates: List[int]):
        """In ``DCFFChannelUnit``, `candidates` is altered after initiation
        with ``DCFFChannelMutator.channel_configs`` imported from file.

        Args:
            candidates (List(int)): candidate list of ``dynamic_ops``.
                In ``DCFFChannelUnit`` list contains one candidate.
        """
        self.candidate_choices = candidates
        for channel in self.input_related:
            if isinstance(channel.module, dynamic_ops.FuseConv2d):
                channel.module.change_mutable_attrs_after_init(
                    'in_channels', candidates)
        for channel in self.output_related:
            if isinstance(channel.module, dynamic_ops.FuseConv2d):
                channel.module.change_mutable_attrs_after_init(
                    'out_channels', candidates)

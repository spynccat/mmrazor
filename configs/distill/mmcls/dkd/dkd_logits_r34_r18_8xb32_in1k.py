_base_ = [
    'mmcls::_base_/datasets/imagenet_bs32.py',
    'mmcls::_base_/schedules/imagenet_bs256.py',
    'mmcls::_base_/default_runtime.py'
]

model = dict(
    _scope_='mmrazor',
    type='SingleTeacherDistill',
    data_preprocessor=dict(
        type='ImgDataPreprocessor',
        # RGB format normalization parameters
        mean=[123.675, 116.28, 103.53],
        std=[58.395, 57.12, 57.375],
        # convert image from BGR to RGB
        bgr_to_rgb=True),
    architecture=dict(
        cfg_path='mmcls::resnet/resnet18_8xb32_in1k.py', pretrained=False),
    teacher=dict(
        cfg_path='mmcls::resnet/resnet34_8xb32_in1k.py', pretrained=True),
    teacher_ckpt='data/razor_checkpoint/resnet34_8xb32_in1k_20210831-f257d4e6.pth',
    distiller=dict(
        type='ConfigurableDistiller',
        student_recorders=dict(
            fc=dict(type='ModuleOutputs', source='head.fc'),
            data_samples=dict(type='ModuleInputs', source='')),
        teacher_recorders=dict(
            fc=dict(type='ModuleOutputs', source='head.fc')),
        distill_losses=dict(
            loss_dkd=dict(type='DKDLoss', tau=1, beta=0.5, loss_weight=1)),
        loss_forward_mappings=dict(
            loss_dkd=dict(
                preds_S=dict(from_student=True, recorder='fc'),
                preds_T=dict(from_student=False, recorder='fc'),
                data_samples=dict(
                    recorder='data_samples', from_student=True, data_idx=1)))))

find_unused_parameters = True

val_cfg = dict(_delete_=True, type='mmrazor.SingleTeacherDistillValLoop')

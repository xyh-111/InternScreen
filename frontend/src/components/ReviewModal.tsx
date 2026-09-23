import { Alert, Form, InputNumber, Modal, Segmented, Switch, Typography } from 'antd';
import { useEffect } from 'react';

import type { InterruptPayload } from '../types';

interface Props {
  open: boolean;
  threadId: string;
  payload: InterruptPayload | null;
  loading: boolean;
  onSubmit: (humanInput: Record<string, unknown>) => void;
  onCancel: () => void;
}

/** 根据 interrupt payload 的 reasons 推导需要人工补录的字段 */
function buildFields(reasons: string[]) {
  const joined = reasons.join('|');
  return {
    duration: joined.includes('时长'),
    days: joined.includes('到岗天数'),
    chengdu: joined.includes('成都'),
    schoolTier: joined.includes('院校'),
  };
}

export default function ReviewModal({
  open,
  threadId,
  payload,
  loading,
  onSubmit,
  onCancel,
}: Props) {
  const [form] = Form.useForm();

  useEffect(() => {
    if (open && payload) {
      form.setFieldsValue({
        internship_duration_months: payload.fields?.internship_duration_months ?? null,
        days_per_week: payload.fields?.days_per_week ?? null,
        chengdu_onsite: payload.fields?.chengdu_onsite ?? true,
      });
    }
  }, [open, payload, form]);

  if (!payload) {
    return null;
  }

  const fields = buildFields(payload.reasons ?? []);

  const handleOk = async () => {
    const values = await form.validateFields();
    const humanInput: Record<string, unknown> = {};

    if (fields.duration && values.internship_duration_months != null) {
      humanInput.internship_duration_months = values.internship_duration_months;
    }
    if (fields.days && values.days_per_week != null) {
      humanInput.days_per_week = values.days_per_week;
    }
    if (fields.chengdu) {
      humanInput.chengdu_onsite = values.chengdu_onsite;
    }
    if (fields.schoolTier && values.school_tier) {
      humanInput.school_tier = values.school_tier;
    }

    onSubmit(humanInput);
  };

  return (
    <Modal
      open={open}
      title="人工复核"
      okText="提交并恢复执行"
      cancelText="稍后处理"
      confirmLoading={loading}
      onOk={handleOk}
      onCancel={onCancel}
      destroyOnHidden
    >
      <Alert
        type="warning"
        showIcon
        style={{ marginBottom: 16 }}
        message={`候选人 ${payload.candidate_id} 需要人工复核`}
        description={
          <>
            <div>复核原因：{payload.reasons?.join('；')}</div>
            <div>复核建议：{payload.suggestion}</div>
            <div>抽取置信度：{payload.field_confidence}</div>
          </>
        }
      />

      <Typography.Paragraph type="secondary" style={{ fontSize: 12 }}>
        thread_id：{threadId}
      </Typography.Paragraph>

      <Form form={form} layout="vertical">
        {fields.duration && (
          <Form.Item name="internship_duration_months" label="可实习月数">
            <InputNumber min={0} max={24} style={{ width: '100%' }} />
          </Form.Item>
        )}
        {fields.days && (
          <Form.Item name="days_per_week" label="每周到岗天数">
            <InputNumber min={1} max={7} style={{ width: '100%' }} />
          </Form.Item>
        )}
        {fields.chengdu && (
          <Form.Item name="chengdu_onsite" label="成都线下" valuePropName="checked">
            <Switch />
          </Form.Item>
        )}
        {fields.schoolTier && (
          <Form.Item
            name="school_tier"
            label="院校层次"
            rules={[{ required: true, message: '请确认院校层次' }]}
          >
            <Segmented
              options={[
                { label: '双一流', value: 'double_first_class' },
                { label: '非双一流', value: 'other' },
              ]}
            />
          </Form.Item>
        )}
      </Form>
    </Modal>
  );
}

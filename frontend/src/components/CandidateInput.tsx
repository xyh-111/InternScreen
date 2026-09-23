import { UploadOutlined } from '@ant-design/icons';
import {
  App,
  Button,
  Card,
  Form,
  Input,
  Segmented,
  Space,
  Tag,
  Tooltip,
  Upload,
} from 'antd';
import { useState } from 'react';

import { uploadPdf, type RunAgentPayload } from '../api/agent';
import type { InputMode } from '../types';

interface Props {
  loading: boolean;
  onRun: (payload: RunAgentPayload) => void;
}

export default function CandidateInput({ loading, onRun }: Props) {
  const { message } = App.useApp();
  const [mode, setMode] = useState<InputMode>('text');
  const [text, setText] = useState('');
  const [filePath, setFilePath] = useState('');
  const [fileName, setFileName] = useState('');
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (file: File) => {
    setUploading(true);
    try {
      const path = await uploadPdf(file);
      setFilePath(path);
      setFileName(file.name);
      message.success(`已上传 ${file.name}`);
    } catch {
      message.error('PDF 上传失败');
    } finally {
      setUploading(false);
    }
    return false;
  };

  const handleSubmit = () => {
    const rawInput = mode === 'text' ? text : filePath;

    if (!rawInput) {
      message.warning(mode === 'text' ? '请粘贴简历文本' : '请先上传 PDF 简历');
      return;
    }

    onRun({
      input_type: mode,
      raw_input: rawInput,
    });
  };

  return (
    <Card className="is-card" title="简历输入" variant="borderless">
      <Form layout="vertical">
        <Form.Item label="输入方式" style={{ marginBottom: 12 }}>
          <Segmented
            value={mode}
            onChange={(value) => setMode(value as InputMode)}
            options={[
              { label: '文本', value: 'text' },
              { label: 'PDF', value: 'pdf' },
            ]}
          />
        </Form.Item>

        {mode === 'text' ? (
          <Form.Item label="简历文本" style={{ marginBottom: 12 }}>
            <Input.TextArea
              rows={9}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="粘贴候选人简历文本……"
            />
          </Form.Item>
        ) : (
          <Form.Item label="PDF 简历" style={{ marginBottom: 12 }}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Upload beforeUpload={handleUpload} maxCount={1} showUploadList={false}>
                <Button icon={<UploadOutlined />} loading={uploading}>
                  选择 PDF 文件
                </Button>
              </Upload>
              {fileName && (
                <Tooltip title={filePath}>
                  <Tag color="blue">{fileName}</Tag>
                </Tooltip>
              )}
            </Space>
          </Form.Item>
        )}

        <Button
          type="primary"
          block
          loading={loading}
          onClick={handleSubmit}
          disabled={uploading}
        >
          简历筛选
        </Button>
      </Form>
    </Card>
  );
}

/**
 * 变量配置组件
 * 管理聊天助手的变量设置
 */
import React from 'react';
import { Button, Input, Select, Switch, Card, Space, Typography, Empty } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { ChatbotVariable } from '../services/chatbot';

const { Text } = Typography;

interface VariableSettingsProps {
  variables: ChatbotVariable[];
  onChange: (variables: ChatbotVariable[]) => void;
}

const VariableSettings: React.FC<VariableSettingsProps> = ({
  variables = [],
  onChange,
}) => {
  const handleAdd = () => {
    const newVar: ChatbotVariable = {
      key: `var_${Date.now()}`,
      name: '',
      type: 'text_input',
      required: false,
    };
    onChange([...variables, newVar]);
  };

  const handleUpdate = (index: number, field: keyof ChatbotVariable, value: any) => {
    const updated = variables.map((v, i) =>
      i === index ? { ...v, [field]: value } : v
    );
    onChange(updated);
  };

  const handleDelete = (index: number) => {
    onChange(variables.filter((_, i) => i !== index));
  };

  return (
    <div>
      <div className="mb-4 flex justify-between items-center">
        <Text strong>变量配置</Text>
        <Button icon={<PlusOutlined />} onClick={handleAdd}>
          添加变量
        </Button>
      </div>

      <Text type="secondary" className="block mb-4">
        变量能使用用户输入表单引入提示词或开场白，你可以试试在提示词中输入 {'{{input}}'}
      </Text>

      {variables.length === 0 ? (
        <Empty description="暂无变量" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <Space direction="vertical" className="w-full" size={12}>
          {variables.map((variable, index) => (
            <Card key={variable.key} size="small">
              <div className="flex gap-3 items-start">
                <div className="flex-1">
                  <div className="mb-2">
                    <Text type="secondary" className="text-xs">变量名</Text>
                    <Input
                      value={variable.name}
                      onChange={(e) => handleUpdate(index, 'name', e.target.value)}
                      placeholder="变量显示名称"
                      size="small"
                    />
                  </div>
                  <div className="mb-2">
                    <Text type="secondary" className="text-xs">Key</Text>
                    <Input
                      value={variable.key}
                      onChange={(e) => handleUpdate(index, 'key', e.target.value)}
                      placeholder="变量键名"
                      size="small"
                    />
                  </div>
                  <div className="flex gap-3">
                    <div className="flex-1">
                      <Text type="secondary" className="text-xs">类型</Text>
                      <Select
                        value={variable.type}
                        onChange={(value) => handleUpdate(index, 'type', value)}
                        className="w-full"
                        size="small"
                        options={[
                          { value: 'text_input', label: '文本输入' },
                          { value: 'paragraph', label: '段落' },
                          { value: 'select', label: '下拉选择' },
                        ]}
                      />
                    </div>
                    <div className="flex items-center gap-1 pt-5">
                      <Text type="secondary" className="text-xs">必填</Text>
                      <Switch
                        checked={variable.required}
                        onChange={(checked) => handleUpdate(index, 'required', checked)}
                        size="small"
                      />
                    </div>
                  </div>
                </div>
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => handleDelete(index)}
                  size="small"
                />
              </div>
            </Card>
          ))}
        </Space>
      )}
    </div>
  );
};

export default VariableSettings;

/**
 * 变量配置组件 — Dify 风格
 * 管理聊天助手的变量设置
 */
import React, { useState } from 'react';
import { Button, Input, Select, Switch, Dropdown, Typography, Empty, Tag, Tooltip, Modal, Form } from 'antd';
import {
  PlusOutlined, DeleteOutlined, InfoCircleOutlined, HolderOutlined,
  FontSizeOutlined, AlignLeftOutlined, DownSquareOutlined,
  NumberOutlined, CheckSquareOutlined, ApiOutlined,
} from '@ant-design/icons';
import { ChatbotVariable, VariableType } from '../services/chatbot';

const { Text } = Typography;

interface VariableSettingsProps {
  variables: ChatbotVariable[];
  onChange: (variables: ChatbotVariable[]) => void;
}

// 变量类型配置
const VARIABLE_TYPES: Array<{
  value: VariableType;
  label: string;
  icon: React.ReactNode;
  color: string;
}> = [
  { value: 'text_input', label: '文本', icon: <FontSizeOutlined />, color: '#1677ff' },
  { value: 'paragraph', label: '段落', icon: <AlignLeftOutlined />, color: '#1677ff' },
  { value: 'select', label: '下拉选项', icon: <DownSquareOutlined />, color: '#1677ff' },
  { value: 'number', label: '数字', icon: <NumberOutlined />, color: '#1677ff' },
  { value: 'checkbox', label: '复选框', icon: <CheckSquareOutlined />, color: '#1677ff' },
  { value: 'api_variable', label: '基于 API 的变量', icon: <ApiOutlined />, color: '#1677ff' },
];

// 获取变量类型配置
const getVariableTypeConfig = (type: VariableType) => {
  return VARIABLE_TYPES.find(t => t.value === type) || VARIABLE_TYPES[0];
};

const VariableSettings: React.FC<VariableSettingsProps> = ({
  variables = [],
  onChange,
}) => {
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editingVariable, setEditingVariable] = useState<ChatbotVariable | null>(null);
  const [editingIndex, setEditingIndex] = useState<number>(-1);
  const [form] = Form.useForm();

  const handleAdd = (type: VariableType) => {
    const newVar: ChatbotVariable = {
      key: `var_${Date.now()}`,
      name: '',
      type,
      required: false,
    };
    setEditingVariable(newVar);
    setEditingIndex(-1);
    form.setFieldsValue(newVar);
    setEditModalVisible(true);
  };

  const handleEdit = (variable: ChatbotVariable, index: number) => {
    setEditingVariable(variable);
    setEditingIndex(index);
    form.setFieldsValue(variable);
    setEditModalVisible(true);
  };

  const handleSave = () => {
    form.validateFields().then(values => {
      if (editingIndex >= 0) {
        // 更新现有变量
        const updated = variables.map((v, i) =>
          i === editingIndex ? { ...v, ...values } : v
        );
        onChange(updated);
      } else {
        // 添加新变量
        onChange([...variables, { ...editingVariable!, ...values }]);
      }
      setEditModalVisible(false);
      form.resetFields();
    });
  };

  const handleDelete = (index: number) => {
    onChange(variables.filter((_, i) => i !== index));
  };

  // 下拉菜单项
  const menuItems = VARIABLE_TYPES.map(type => ({
    key: type.value,
    icon: React.cloneElement(type.icon as React.ReactElement, {
      style: { color: type.color }
    }),
    label: type.label,
    onClick: () => handleAdd(type.value),
  }));

  return (
    <div>
      {/* 头部 */}
      <div className="flex justify-between items-center mb-3">
        <div className="flex items-center gap-1">
          <Text strong>变量</Text>
          <Tooltip title="变量能使用用户输入表单引入提示词或开场白">
            <InfoCircleOutlined className="text-gray-400 text-xs cursor-help" />
          </Tooltip>
        </div>
        <Dropdown menu={{ items: menuItems }} trigger={['click']}>
          <Button type="primary" ghost size="small" icon={<PlusOutlined />}>
            添加
          </Button>
        </Dropdown>
      </div>

      {/* 描述 */}
      <Text type="secondary" className="block mb-4 text-xs">
        变量能使用用户输入表单引入提示词或开场白，你可以试试在提示词中输入 {'{{input}}'}
      </Text>

      {/* 变量列表 */}
      {variables.length === 0 ? (
        <Empty description="暂无变量" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        <div className="space-y-2">
          {variables.map((variable, index) => {
            const typeConfig = getVariableTypeConfig(variable.type);
            return (
              <div
                key={variable.key}
                className="flex items-center justify-between p-3 bg-white border border-gray-200 rounded-lg hover:border-blue-300 transition-colors cursor-pointer group"
                onClick={() => handleEdit(variable, index)}
              >
                <div className="flex items-center gap-3">
                  <HolderOutlined className="text-gray-300 cursor-move opacity-0 group-hover:opacity-100 transition-opacity" />
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-800">
                      {variable.name || '未命名变量'}
                    </span>
                    <Tag
                      icon={typeConfig.icon}
                      color={typeConfig.color}
                      className="!m-0"
                    >
                      {typeConfig.label}
                    </Tag>
                    {variable.required && (
                      <Tag color="red" className="!m-0">必填</Tag>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Tooltip title="删除">
                    <Button
                      type="text"
                      danger
                      size="small"
                      icon={<DeleteOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(index);
                      }}
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                    />
                  </Tooltip>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 编辑弹窗 */}
      <Modal
        title={editingIndex >= 0 ? '编辑变量' : '添加变量'}
        open={editModalVisible}
        onOk={handleSave}
        onCancel={() => {
          setEditModalVisible(false);
          form.resetFields();
        }}
        width={500}
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item
            name="name"
            label="变量名称"
            rules={[{ required: true, message: '请输入变量名称' }]}
          >
            <Input placeholder="请输入变量名称" />
          </Form.Item>

          <Form.Item
            name="key"
            label="变量 Key"
            rules={[{ required: true, message: '请输入变量 Key' }]}
          >
            <Input placeholder="请输入变量 Key" disabled={editingIndex >= 0} />
          </Form.Item>

          <Form.Item name="type" label="变量类型" rules={[{ required: true }]}>
            <Select placeholder="请选择变量类型">
              {VARIABLE_TYPES.map(type => (
                <Select.Option key={type.value} value={type.value}>
                  <div className="flex items-center gap-2">
                    <span style={{ color: type.color }}>{type.icon}</span>
                    <span>{type.label}</span>
                  </div>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="请输入变量描述" />
          </Form.Item>

          <Form.Item name="required" label="必填" valuePropName="checked">
            <Switch />
          </Form.Item>

          <Form.Item name="default" label="默认值">
            <Input placeholder="请输入默认值" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default VariableSettings;

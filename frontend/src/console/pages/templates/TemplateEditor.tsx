import React, { useState, useEffect } from "react";
import { Card, Button, Input, Select, Textarea, Tabs, Alert } from "@/components/ui";

interface TemplateParameter {
  name: string;
  type: string;
  description: string;
  default?: any;
  required: boolean;
  enum_values?: any[];
  placeholder?: string;
  help_text?: string;
}

interface TemplateNode {
  id: string;
  type: string;
  name: string;
  description: string;
  config: Record<string, any>;
  position: { x: number; y: number };
}

interface TemplateEdge {
  source: string;
  target: string;
  condition?: string;
  label?: string;
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  status: string;
  parameters: TemplateParameter[];
  nodes: TemplateNode[];
  edges: TemplateEdge[];
  tags: string[];
  author: string;
  created_at: string;
  updated_at: string;
  usage_count: number;
  rating: number;
}

interface TemplateEditorProps {
  templateId?: string;
  onSave?: (template: WorkflowTemplate) => void;
  onCancel?: () => void;
}

export function TemplateEditor({ templateId, onSave, onCancel }: TemplateEditorProps) {
  const [template, setTemplate] = useState<Partial<WorkflowTemplate>>({
    name: "",
    description: "",
    category: "custom",
    version: "1.0.0",
    status: "draft",
    parameters: [],
    nodes: [],
    edges: [],
    tags: [],
  });

  const [activeTab, setActiveTab] = useState("basic");
  const [errors, setErrors] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  // Load template if editing
  useEffect(() => {
    if (templateId) {
      loadTemplate();
    }
  }, [templateId]);

  const loadTemplate = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/templates/${templateId}`);
      if (response.ok) {
        const data = await response.json();
        setTemplate(data);
      }
    } catch (error) {
      console.error("Failed to load template:", error);
      setErrors(["Failed to load template"]);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setErrors([]);

      const method = templateId ? "PUT" : "POST";
      const url = templateId ? `/api/v1/templates/${templateId}` : "/api/v1/templates";

      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(template),
      });

      if (!response.ok) {
        const error = await response.json();
        setErrors([error.detail || "Failed to save template"]);
        return;
      }

      const result = await response.json();
      onSave?.(result);
    } catch (error) {
      console.error("Failed to save template:", error);
      setErrors(["Failed to save template"]);
    } finally {
      setLoading(false);
    }
  };

  const addParameter = () => {
    setTemplate({
      ...template,
      parameters: [
        ...(template.parameters || []),
        {
          name: "",
          type: "string",
          description: "",
          required: false,
          enum_values: [],
        },
      ],
    });
  };

  const updateParameter = (index: number, field: string, value: any) => {
    const params = [...(template.parameters || [])];
    params[index] = { ...params[index], [field]: value };
    setTemplate({ ...template, parameters: params });
  };

  const removeParameter = (index: number) => {
    const params = template.parameters?.filter((_, i) => i !== index) || [];
    setTemplate({ ...template, parameters: params });
  };

  const addNode = () => {
    setTemplate({
      ...template,
      nodes: [
        ...(template.nodes || []),
        {
          id: `node_${Date.now()}`,
          type: "transform",
          name: "",
          description: "",
          config: {},
          position: { x: 0, y: 0 },
        },
      ],
    });
  };

  const updateNode = (index: number, field: string, value: any) => {
    const nodes = [...(template.nodes || [])];
    nodes[index] = { ...nodes[index], [field]: value };
    setTemplate({ ...template, nodes });
  };

  const removeNode = (index: number) => {
    const nodes = template.nodes?.filter((_, i) => i !== index) || [];
    setTemplate({ ...template, nodes });
  };

  return (
    <div className="space-y-6">
      {errors.length > 0 && (
        <Alert variant="destructive">
          <div className="space-y-1">
            {errors.map((error, i) => (
              <div key={i}>{error}</div>
            ))}
          </div>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab("basic")}
            className={`px-4 py-2 rounded ${activeTab === "basic" ? "bg-blue-500 text-white" : "bg-gray-200"}`}
          >
            Basic Info
          </button>
          <button
            onClick={() => setActiveTab("parameters")}
            className={`px-4 py-2 rounded ${activeTab === "parameters" ? "bg-blue-500 text-white" : "bg-gray-200"}`}
          >
            Parameters
          </button>
          <button
            onClick={() => setActiveTab("nodes")}
            className={`px-4 py-2 rounded ${activeTab === "nodes" ? "bg-blue-500 text-white" : "bg-gray-200"}`}
          >
            Nodes
          </button>
        </div>

        {/* Basic Info Tab */}
        {activeTab === "basic" && (
          <div className="space-y-4 mt-4">
            <div>
              <label htmlFor="template-name" className="block text-sm font-medium mb-1">Template Name</label>
              <Input
                id="template-name"
                value={template.name || ""}
                onChange={(e) => setTemplate({ ...template, name: e.target.value })}
                placeholder="Enter template name"
              />
            </div>

            <div>
              <label htmlFor="template-description" className="block text-sm font-medium mb-1">Description</label>
              <Textarea
                id="template-description"
                value={template.description || ""}
                onChange={(e) => setTemplate({ ...template, description: e.target.value })}
                placeholder="Enter template description"
                rows={4}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="template-category" className="block text-sm font-medium mb-1">Category</label>
                <Select
                  id="template-category"
                  value={template.category || "custom"}
                  onChange={(e) => setTemplate({ ...template, category: e.target.value })}
                >
                  <option value="data_processing">Data Processing</option>
                  <option value="web_scraping">Web Scraping</option>
                  <option value="code_review">Code Review</option>
                  <option value="documentation">Documentation</option>
                  <option value="custom">Custom</option>
                </Select>
              </div>

              <div>
                <label htmlFor="template-version" className="block text-sm font-medium mb-1">Version</label>
                <Input
                  id="template-version"
                  value={template.version || "1.0.0"}
                  onChange={(e) => setTemplate({ ...template, version: e.target.value })}
                  placeholder="1.0.0"
                />
              </div>
            </div>

            <div>
              <label htmlFor="template-tags" className="block text-sm font-medium mb-1">Tags</label>
              <Input
                id="template-tags"
                value={(template.tags || []).join(", ")}
                onChange={(e) => setTemplate({ ...template, tags: e.target.value.split(",").map((t) => t.trim()) })}
                placeholder="tag1, tag2, tag3"
              />
            </div>
          </div>
        )}

        {/* Parameters Tab */}
        {activeTab === "parameters" && (
          <div className="space-y-4 mt-4">
            <Button onClick={addParameter} variant="outline">
              Add Parameter
            </Button>

            {(template.parameters || []).map((param, index) => (
              <Card key={index} className="p-4">
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    value={param.name}
                    onChange={(e) => updateParameter(index, "name", e.target.value)}
                    placeholder="Parameter name"
                  />
                  <Select
                    value={param.type}
                    onChange={(e) => updateParameter(index, "type", e.target.value)}
                  >
                    <option value="string">String</option>
                    <option value="number">Number</option>
                    <option value="boolean">Boolean</option>
                    <option value="array">Array</option>
                    <option value="object">Object</option>
                    <option value="select">Select</option>
                  </Select>
                </div>

                <Textarea
                  value={param.description}
                  onChange={(e) => updateParameter(index, "description", e.target.value)}
                  placeholder="Description"
                  rows={2}
                  className="mt-2"
                />

                <div className="flex gap-2 mt-2">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={param.required}
                      onChange={(e) => updateParameter(index, "required", e.target.checked)}
                    />
                    Required
                  </label>
                  <Button
                    onClick={() => removeParameter(index)}
                    variant="destructive"
                    size="sm"
                  >
                    Remove
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}

        {/* Nodes Tab */}
        {activeTab === "nodes" && (
          <div className="space-y-4 mt-4">
            <Button onClick={addNode} variant="outline">
              Add Node
            </Button>

            {(template.nodes || []).map((node, index) => (
              <Card key={index} className="p-4">
                <div className="grid grid-cols-2 gap-4">
                  <Input
                    value={node.id}
                    onChange={(e) => updateNode(index, "id", e.target.value)}
                    placeholder="Node ID"
                  />
                  <Select
                    value={node.type}
                    onChange={(e) => updateNode(index, "type", e.target.value)}
                  >
                    <option value="input">Input</option>
                    <option value="output">Output</option>
                    <option value="transform">Transform</option>
                    <option value="tool">Tool</option>
                    <option value="agent">Agent</option>
                    <option value="condition">Condition</option>
                  </Select>
                </div>

                <Input
                  value={node.name}
                  onChange={(e) => updateNode(index, "name", e.target.value)}
                  placeholder="Node name"
                  className="mt-2"
                />

                <Button
                  onClick={() => removeNode(index)}
                  variant="destructive"
                  size="sm"
                  className="mt-2"
                >
                  Remove
                </Button>
              </Card>
            ))}
          </div>
        )}
      </Tabs>

      <div className="flex gap-2 justify-end">
        <Button onClick={onCancel} variant="outline">
          Cancel
        </Button>
        <Button onClick={handleSave} disabled={loading}>
          {loading ? "Saving..." : "Save Template"}
        </Button>
      </div>
    </div>
  );
}

export default TemplateEditor;

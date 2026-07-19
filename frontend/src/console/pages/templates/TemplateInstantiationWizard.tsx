import React, { useState, useEffect } from "react";
import { Card, Button, Input, Select, Textarea, Checkbox, Alert, Spinner, StepIndicator } from "@/components/ui";

interface TemplateParameter {
  name: string;
  type: string;
  description: string;
  default?: any;
  required: boolean;
  enum_values?: any[];
  placeholder?: string;
  help_text?: string;
  min_value?: number;
  max_value?: number;
  min_length?: number;
  max_length?: number;
}

interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: string;
  version: string;
  parameters: TemplateParameter[];
  nodes: any[];
  edges: any[];
  tags: string[];
  author: string;
  example_inputs?: Record<string, any>;
}

interface TemplateInstantiationWizardProps {
  template: WorkflowTemplate;
  onComplete?: (workflowId: string) => void;
  onCancel?: () => void;
}

export function TemplateInstantiationWizard({
  template,
  onComplete,
  onCancel,
}: TemplateInstantiationWizardProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [parameters, setParameters] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // Initialize parameters with defaults
  useEffect(() => {
    const initialParams: Record<string, any> = {};
    template.parameters.forEach((param) => {
      initialParams[param.name] = param.default || "";
    });
    setParameters(initialParams);
  }, [template]);

  const handleParameterChange = (name: string, value: any) => {
    setParameters({ ...parameters, [name]: value });
    // Clear error for this parameter
    if (errors[name]) {
      const newErrors = { ...errors };
      delete newErrors[name];
      setErrors(newErrors);
    }
  };

  const validateCurrentStep = (): boolean => {
    const stepParams = template.parameters.slice(
      currentStep * 3,
      (currentStep + 1) * 3
    );

    const newErrors: Record<string, string> = {};
    let isValid = true;

    stepParams.forEach((param) => {
      const value = parameters[param.name];

      // Check required
      if (param.required && !value) {
        newErrors[param.name] = `${param.name} is required`;
        isValid = false;
      }

      // Validate type
      if (value !== undefined && value !== "") {
        if (param.type === "number") {
          if (isNaN(value)) {
            newErrors[param.name] = "Must be a number";
            isValid = false;
          } else if (param.min_value !== undefined && value < param.min_value) {
            newErrors[param.name] = `Must be at least ${param.min_value}`;
            isValid = false;
          } else if (param.max_value !== undefined && value > param.max_value) {
            newErrors[param.name] = `Must be at most ${param.max_value}`;
            isValid = false;
          }
        } else if (param.type === "string") {
          if (param.min_length && value.length < param.min_length) {
            newErrors[param.name] = `Must be at least ${param.min_length} characters`;
            isValid = false;
          } else if (param.max_length && value.length > param.max_length) {
            newErrors[param.name] = `Must be at most ${param.max_length} characters`;
            isValid = false;
          }
        }
      }
    });

    setErrors(newErrors);
    return isValid;
  };

  const handleNext = () => {
    if (validateCurrentStep()) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    setCurrentStep(currentStep - 1);
  };

  const handleInstantiate = async () => {
    try {
      setLoading(true);
      setValidationErrors([]);

      const response = await fetch(`/api/v1/templates/${template.id}/instantiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ parameters }),
      });

      if (!response.ok) {
        const error = await response.json();
        setValidationErrors(
          Array.isArray(error.detail) ? error.detail : [error.detail || "Failed to instantiate template"]
        );
        return;
      }

      const result = await response.json();
      onComplete?.(result.workflow_id);
    } catch (error) {
      console.error("Failed to instantiate template:", error);
      setValidationErrors(["Failed to instantiate template"]);
    } finally {
      setLoading(false);
    }
  };

  const totalSteps = Math.ceil(template.parameters.length / 3);
  const currentStepParams = template.parameters.slice(
    currentStep * 3,
    (currentStep + 1) * 3
  );

  const renderParameterInput = (param: TemplateParameter) => {
    const value = parameters[param.name];
    const error = errors[param.name];

    switch (param.type) {
      case "number":
        return (
          <div key={param.name} className="space-y-2">
            <label className="block text-sm font-medium">
              {param.name}
              {param.required && <span className="text-red-500">*</span>}
            </label>
            <Input
              type="number"
              value={value || ""}
              onChange={(e) => handleParameterChange(param.name, e.target.value)}
              placeholder={param.placeholder || "Enter a number"}
              min={param.min_value}
              max={param.max_value}
            />
            {param.help_text && <p className="text-xs text-gray-600">{param.help_text}</p>}
            {error && <p className="text-xs text-red-500">{error}</p>}
          </div>
        );

      case "boolean":
        return (
          <div key={param.name} className="space-y-2">
            <label className="flex items-center gap-2">
              <Checkbox
                checked={value || false}
                onChange={(e) => handleParameterChange(param.name, e.target.checked)}
              />
              <span className="text-sm font-medium">{param.name}</span>
            </label>
            {param.help_text && <p className="text-xs text-gray-600">{param.help_text}</p>}
          </div>
        );

      case "select":
      case "multiselect":
        return (
          <div key={param.name} className="space-y-2">
            <label className="block text-sm font-medium">
              {param.name}
              {param.required && <span className="text-red-500">*</span>}
            </label>
            <Select
              value={value || ""}
              onChange={(e) => handleParameterChange(param.name, e.target.value)}
            >
              <option value="">Select an option</option>
              {param.enum_values?.map((val) => (
                <option key={val} value={val}>
                  {val}
                </option>
              ))}
            </Select>
            {param.help_text && <p className="text-xs text-gray-600">{param.help_text}</p>}
            {error && <p className="text-xs text-red-500">{error}</p>}
          </div>
        );

      case "array":
        return (
          <div key={param.name} className="space-y-2">
            <label className="block text-sm font-medium">
              {param.name}
              {param.required && <span className="text-red-500">*</span>}
            </label>
            <Textarea
              value={Array.isArray(value) ? value.join("\n") : ""}
              onChange={(e) =>
                handleParameterChange(param.name, e.target.value.split("\n").filter((v) => v))
              }
              placeholder="Enter one item per line"
              rows={4}
            />
            {param.help_text && <p className="text-xs text-gray-600">{param.help_text}</p>}
            {error && <p className="text-xs text-red-500">{error}</p>}
          </div>
        );

      case "object":
        return (
          <div key={param.name} className="space-y-2">
            <label className="block text-sm font-medium">
              {param.name}
              {param.required && <span className="text-red-500">*</span>}
            </label>
            <Textarea
              value={typeof value === "object" ? JSON.stringify(value, null, 2) : ""}
              onChange={(e) => {
                try {
                  handleParameterChange(param.name, JSON.parse(e.target.value));
                } catch {
                  // Invalid JSON, keep as string
                }
              }}
              placeholder='{"key": "value"}'
              rows={4}
            />
            {param.help_text && <p className="text-xs text-gray-600">{param.help_text}</p>}
            {error && <p className="text-xs text-red-500">{error}</p>}
          </div>
        );

      default:
        return (
          <div key={param.name} className="space-y-2">
            <label className="block text-sm font-medium">
              {param.name}
              {param.required && <span className="text-red-500">*</span>}
            </label>
            <Input
              value={value || ""}
              onChange={(e) => handleParameterChange(param.name, e.target.value)}
              placeholder={param.placeholder || "Enter a value"}
              maxLength={param.max_length}
            />
            {param.help_text && <p className="text-xs text-gray-600">{param.help_text}</p>}
            {error && <p className="text-xs text-red-500">{error}</p>}
          </div>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <section className="rounded-2xl border bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold mb-2">{template.name}</h1>
        <p className="text-gray-600">{template.description}</p>
      </section>

      {/* Step Indicator */}
      {totalSteps > 1 && (
        <StepIndicator
          steps={Array.from({ length: totalSteps }, (_, i) => `Step ${i + 1}`)}
          currentStep={currentStep}
        />
      )}

      {/* Validation Errors */}
      {validationErrors.length > 0 && (
        <Alert variant="destructive">
          <div className="space-y-1">
            {validationErrors.map((error, i) => (
              <div key={i}>{error}</div>
            ))}
          </div>
        </Alert>
      )}

      {/* Parameters */}
      <Card className="p-6">
        <div className="space-y-4">
          {currentStepParams.map((param) => renderParameterInput(param))}
        </div>
      </Card>

      {/* Navigation */}
      <div className="flex gap-2 justify-between">
        <div className="flex gap-2">
          <Button
            onClick={handlePrevious}
            disabled={currentStep === 0}
            variant="outline"
          >
            Previous
          </Button>
          {currentStep < totalSteps - 1 && (
            <Button onClick={handleNext}>
              Next
            </Button>
          )}
        </div>

        <div className="flex gap-2">
          <Button onClick={onCancel} variant="outline">
            Cancel
          </Button>
          {currentStep === totalSteps - 1 && (
            <Button
              onClick={handleInstantiate}
              disabled={loading}
            >
              {loading ? <Spinner /> : "Create Workflow"}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

export default TemplateInstantiationWizard;

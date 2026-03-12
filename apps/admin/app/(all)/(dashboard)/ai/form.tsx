/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useForm, useWatch } from "react-hook-form";
import { Lightbulb } from "lucide-react";
import { Button } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration, TInstanceAIConfigurationKeys } from "@plane/types";
// components
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { ControllerInput } from "@/components/common/controller-input";
// hooks
import { useInstance } from "@/hooks/store";

type IInstanceAIForm = {
  config: IFormattedInstanceConfiguration;
};

type AIFormValues = Record<TInstanceAIConfigurationKeys, string>;

export function InstanceAIForm(props: IInstanceAIForm) {
  const { config } = props;
  // store
  const { updateInstanceConfigurations } = useInstance();
  // form data
  // Determine if custom provider should be shown (when base_url is configured)
  const hasCustomBaseUrl = Boolean(config["LLM_BASE_URL"]);
  const initialProvider = hasCustomBaseUrl ? "custom" : config["LLM_PROVIDER"] || "openai";

  const {
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<AIFormValues>({
    defaultValues: {
      LLM_API_KEY: config["LLM_API_KEY"],
      LLM_MODEL: config["LLM_MODEL"],
      LLM_PROVIDER: initialProvider,
      LLM_BASE_URL: config["LLM_BASE_URL"] || "",
    },
  });

  const selectedProvider = useWatch({ control, name: "LLM_PROVIDER" });

  const providerOptions = [
    { value: "openai", label: "OpenAI" },
    { value: "anthropic", label: "Anthropic" },
    { value: "gemini", label: "Google Gemini" },
    { value: "custom", label: "Custom (OpenRouter, etc.)" },
  ];

  const getModelPlaceholder = () => {
    switch (selectedProvider) {
      case "anthropic":
        return "claude-3-sonnet-20240229";
      case "gemini":
        return "gemini-pro";
      case "custom":
        return "e.g., anthropic/claude-3.5-sonnet";
      default:
        return "gpt-4o-mini";
    }
  };

  const aiFormFields: TControllerInputFormField[] = [
    {
      key: "LLM_PROVIDER",
      type: "select",
      label: "Provider",
      description: "Select your LLM provider. Choose 'Custom' for OpenRouter or self-hosted APIs.",
      placeholder: "Select provider",
      error: Boolean(errors.LLM_PROVIDER),
      required: false,
      options: providerOptions,
    },
    {
      key: "LLM_MODEL",
      type: "text",
      label: "Model",
      description:
        selectedProvider === "custom"
          ? "Enter the model name as required by your provider (e.g., anthropic/claude-3.5-sonnet for OpenRouter)."
          : "Enter the model name to use.",
      placeholder: getModelPlaceholder(),
      error: Boolean(errors.LLM_MODEL),
      required: false,
    },
    {
      key: "LLM_API_KEY",
      type: "password",
      label: "API Key",
      description:
        selectedProvider === "custom"
          ? "Enter your API key from your provider (e.g., OpenRouter API key)."
          : "Enter your API key from the selected provider.",
      placeholder: "sk-...",
      error: Boolean(errors.LLM_API_KEY),
      required: false,
    },
    ...(selectedProvider === "custom"
      ? [
          {
            key: "LLM_BASE_URL" as const,
            type: "text" as const,
            label: "Base URL",
            description: (
              <>
                Custom API endpoint URL (OpenAI-compatible). Examples:{" "}
                <span className="text-accent-primary">https://openrouter.ai/api/v1</span>
              </>
            ),
            placeholder: "https://openrouter.ai/api/v1",
            error: Boolean(errors.LLM_BASE_URL),
            required: false,
          },
        ]
      : []),
  ];

  const onSubmit = async (formData: AIFormValues) => {
    const payload: Partial<AIFormValues> = { ...formData };

    // Clear base_url for built-in providers (non-custom)
    if (payload.LLM_PROVIDER !== "custom") {
      payload.LLM_BASE_URL = "";
    }

    await updateInstanceConfigurations(payload)
      .then(() =>
        setToast({
          type: TOAST_TYPE.SUCCESS,
          title: "Success",
          message: "AI Settings updated successfully",
        })
      )
      .catch((err) => console.error(err));
  };

  return (
    <div className="space-y-8">
      <div className="space-y-3">
        <div>
          <div className="pb-1 text-18 font-medium text-primary">AI Configuration</div>
          <div className="text-13 font-regular text-tertiary">
            Configure your LLM provider. Supports OpenAI, Anthropic, Gemini, or custom OpenAI-compatible APIs
            (OpenRouter, etc.).
          </div>
        </div>
        <div className="grid-col grid w-full grid-cols-1 items-center justify-between gap-x-12 gap-y-8 lg:grid-cols-3">
          {aiFormFields.map((field) => (
            <ControllerInput
              key={field.key}
              control={control}
              type={field.type}
              name={field.key}
              label={field.label}
              description={field.description}
              placeholder={field.placeholder}
              error={field.error}
              required={field.required}
              options={field.options}
            />
          ))}
        </div>
      </div>

      <div className="flex flex-col items-start gap-4">
        <Button variant="primary" size="lg" onClick={handleSubmit(onSubmit)} loading={isSubmitting}>
          {isSubmitting ? "Saving" : "Save changes"}
        </Button>

        <div className="relative inline-flex items-center gap-1.5 rounded-sm border border-accent-subtle bg-accent-subtle px-4 py-2 text-caption-sm-regular text-accent-secondary">
          <Lightbulb className="size-4" />
          <div>
            For OpenRouter, use your OpenRouter API key and set the Base URL to{" "}
            <span className="font-medium">https://openrouter.ai/api/v1</span>
          </div>
        </div>
      </div>
    </div>
  );
}

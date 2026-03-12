/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { useState } from "react";
import type { Control } from "react-hook-form";
import { Controller } from "react-hook-form";
// icons
import { Eye, EyeOff } from "lucide-react";
// plane internal packages
import { Input } from "@plane/ui";
import { cn } from "@plane/utils";

type SelectOption = {
  value: string;
  label: string;
};

type Props<T extends Record<string, string>> = {
  control: Control<T>;
  type: "text" | "password" | "select";
  name: keyof T & string;
  label: string;
  description?: string | React.ReactNode;
  placeholder: string;
  error: boolean;
  required: boolean;
  options?: SelectOption[];
};

export type TControllerInputFormField = {
  key: string;
  type: "text" | "password" | "select";
  label: string;
  description?: string | React.ReactNode;
  placeholder: string;
  error: boolean;
  required: boolean;
  options?: SelectOption[];
};

export function ControllerInput<T extends Record<string, string>>(props: Props<T>) {
  const { name, control, type, label, description, placeholder, error, required, options } = props;
  // states
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="flex flex-col gap-1">
      <h4 className="text-13 text-tertiary">{label}</h4>
      <div className="relative">
        <Controller
          control={control}
          name={name}
          rules={{ required: required ? `${label} is required.` : false }}
          render={({ field: { value, onChange, ref } }) =>
            type === "select" ? (
              <select
                id={name}
                name={name}
                value={value}
                onChange={onChange}
                ref={ref}
                className={cn(
                  "w-full rounded-md border border-subtle bg-transparent px-3 py-2 text-13 font-medium text-primary outline-none focus:ring-1 focus:ring-accent-primary",
                  { "border-danger-primary": error }
                )}
              >
                {options?.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            ) : (
              <Input
                id={name}
                name={name}
                type={type === "password" && showPassword ? "text" : type}
                value={value}
                onChange={onChange}
                ref={ref}
                hasError={error}
                placeholder={placeholder}
                className={cn("w-full rounded-md font-medium", {
                  "pr-10": type === "password",
                })}
              />
            )
          }
        />
        {type === "password" &&
          (showPassword ? (
            <button
              tabIndex={-1}
              className="absolute top-2.5 right-3 flex items-center justify-center text-placeholder"
              onClick={() => setShowPassword(false)}
            >
              <EyeOff className="h-4 w-4" />
            </button>
          ) : (
            <button
              tabIndex={-1}
              className="absolute top-2.5 right-3 flex items-center justify-center text-placeholder"
              onClick={() => setShowPassword(true)}
            >
              <Eye className="h-4 w-4" />
            </button>
          ))}
      </div>
      {description && <p className="pt-0.5 text-11 text-tertiary">{description}</p>}
    </div>
  );
}

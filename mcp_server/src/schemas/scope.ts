import { z } from "zod";

export const scopeInputSchema = {
  product_code: z.string().min(1).optional(),
  project_code: z.string().min(1).optional(),
  app_code: z.string().min(1).optional(),
};

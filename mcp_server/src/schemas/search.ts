import { z } from "zod";

import { scopeInputSchema } from "./scope.js";

export const searchInputSchema = {
  ...scopeInputSchema,
  query: z.string().min(1),
  top_k: z.number().int().min(1).max(20).optional(),
};

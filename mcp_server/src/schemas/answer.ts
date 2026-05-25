import { z } from "zod";

import { scopeInputSchema } from "./scope.js";

export const answerInputSchema = {
  ...scopeInputSchema,
  query: z.string().min(1),
};

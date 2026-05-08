import type { ProjectResponse } from "@/lib/api/endpoints/projects";
import type { ProductResponse } from "@/lib/api/products";

export interface ProductProjectGroup {
  product: ProductResponse;
  projects: ProjectResponse[];
  totalApps: number;
  matchedBy: "product" | "project" | "none";
}

function includesKeyword(value: string | null | undefined, keyword: string) {
  return (value ?? "").toLowerCase().includes(keyword);
}

export function buildProductProjectGroups(args: {
  products: ProductResponse[];
  projects: ProjectResponse[];
  search: string;
}): ProductProjectGroup[] {
  const keyword = args.search.trim().toLowerCase();
  const projectsByProductId = new Map<number, ProjectResponse[]>();
  const groups: ProductProjectGroup[] = [];

  for (const project of args.projects) {
    const group = projectsByProductId.get(project.product_id) ?? [];
    group.push(project);
    projectsByProductId.set(project.product_id, group);
  }

  for (const product of args.products) {
    const groupedProjects = projectsByProductId.get(product.id) ?? [];
    const totalApps = groupedProjects.reduce((sum, project) => sum + project.app_count, 0);

    if (!keyword) {
      groups.push({ product, projects: groupedProjects, totalApps, matchedBy: "none" });
      continue;
    }

    const productMatched =
      includesKeyword(product.name, keyword) ||
      includesKeyword(product.code, keyword) ||
      includesKeyword(product.description, keyword);

    if (productMatched) {
      groups.push({ product, projects: groupedProjects, totalApps, matchedBy: "product" });
      continue;
    }

    const matchedProjects = groupedProjects.filter(
      (project) =>
        includesKeyword(project.name, keyword) ||
        includesKeyword(project.code, keyword) ||
        includesKeyword(project.description, keyword),
    );

    if (matchedProjects.length === 0) {
      continue;
    }

    groups.push({
      product,
      projects: matchedProjects,
      totalApps,
      matchedBy: "project",
    });
  }

  return groups;
}

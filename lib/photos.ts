import photosData from "@/data/photos.json";
import type { Category, Photo } from "./types";

const photos = photosData as unknown as Photo[];

export function getAllPhotos(): Photo[] {
  return [...photos].sort((a, b) => b.date.localeCompare(a.date));
}

export function getPhotoBySlug(slug: string): Photo | undefined {
  return photos.find((p) => p.slug === slug);
}

export function getCategories(): Category[] {
  const set = new Set<Category>(photos.map((p) => p.category));
  return Array.from(set).sort();
}

export function getPhotosByCategory(category: Category): Photo[] {
  return getAllPhotos().filter((p) => p.category === category);
}

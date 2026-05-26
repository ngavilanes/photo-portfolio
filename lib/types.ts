export type Category = "Portrait" | "Landscape" | "Street";

export interface PhotoExif {
  camera?: string;
  lens?: string;
  focalLength?: string;
  aperture?: string;
  shutterSpeed?: string;
  iso?: string;
}

export interface Photo {
  id: string;
  slug: string;
  title: string;
  description?: string;
  category: Category;
  tags: string[];
  date: string; // ISO 8601
  src: string; // full-resolution image URL
  thumbnail: string; // smaller URL used in the gallery grid
  width: number; // intrinsic full-res width
  height: number; // intrinsic full-res height
  blurDataURL?: string; // optional; falls back to generated shimmer
  exif?: PhotoExif;
}

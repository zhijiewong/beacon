/** @type {import('next').NextConfig} */
// Static export so it hosts free on GitHub Pages / Cloudflare / Netlify.
// For a project Pages site set BASE_PATH=/beacon-index (the repo name).
const basePath = process.env.BASE_PATH || "";
const nextConfig = {
  output: "export",
  basePath,
  assetPrefix: basePath || undefined,
  images: { unoptimized: true },
  trailingSlash: true,
};
export default nextConfig;

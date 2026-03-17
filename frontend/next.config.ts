import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["remark-gfm", "react-markdown", "rehype-raw"],
};

export default nextConfig;

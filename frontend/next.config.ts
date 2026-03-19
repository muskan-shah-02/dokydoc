import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["remark-gfm", "react-markdown", "rehype-raw"],
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;

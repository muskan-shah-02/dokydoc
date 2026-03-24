import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  transpilePackages: ["remark-gfm", "react-markdown", "rehype-raw"],
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;

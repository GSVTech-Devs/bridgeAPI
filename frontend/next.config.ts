import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // until-async (MSW v2 dep) is pure ESM — must be transpiled for Jest
  transpilePackages: ["until-async"],
};

export default nextConfig;

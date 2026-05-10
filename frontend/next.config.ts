import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://bd_legal_core_api:8001/api/:path*",
      },
    ];
  },
};

export default nextConfig;

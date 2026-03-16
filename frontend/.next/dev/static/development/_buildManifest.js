self.__BUILD_MANIFEST = {
  "/": [
    "static/chunks/pages/index.js"
  ],
  "__rewrites": {
    "afterFiles": [],
    "beforeFiles": [
      {
        "source": "/api/:path*"
      }
    ],
    "fallback": []
  },
  "sortedPages": [
    "/",
    "/_app",
    "/_error"
  ]
};self.__BUILD_MANIFEST_CB && self.__BUILD_MANIFEST_CB()
package web

import (
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

func SPA(directory string) http.Handler {
	files := http.FileServer(http.Dir(directory))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cleanPath := filepath.Clean(strings.TrimPrefix(r.URL.Path, "/"))
		if cleanPath == "." {
			cleanPath = "index.html"
		}
		if _, err := os.Stat(filepath.Join(directory, cleanPath)); err != nil {
			r.URL.Path = "/index.html"
		}
		files.ServeHTTP(w, r)
	})
}

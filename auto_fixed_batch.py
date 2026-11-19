#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os
import re
import sys
import time
import urllib.request

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.interpolate import (
    CloughTocher2DInterpolator,
    LinearNDInterpolator,
    RegularGridInterpolator,
)
from scipy.spatial import Delaunay, cKDTree

# ==========================================
# DEFAULT CONFIGURATIONS
# ==========================================
INCLUDE_ECMWF = False       # True = รวม ECMWF / False = ไม่เอา ECMWF
TEMPLATE_FILE = "DA_X44_boundary_coordinates.xlsx"  # ใช้เมื่อไม่ระบุ -t
OUTPUT_DIR = "output"       # ใช้เมื่อไม่ระบุ -o
DEFAULT_METHOD = "kriging"  # ใช้เมื่อไม่ระบุ -m

UTM_EPSG = 32647  # UTM zone 47N, WGS84
IDW_NEIGHBORS = 8


# ==========================================
# 1. FETCH & DOWNLOAD MODULE (Native urllib)
# ==========================================
def fetch_and_download_latest_nwp():
    """Fetch https://hpc.tmd.go.th/download, check local cache, and download if needed."""
    web_url = "https://hpc.tmd.go.th/download"
    print(f"[1/2] Fetching web page: {web_url} ...")

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    try:
        req = urllib.request.Request(web_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            html_content = response.read().decode("utf-8")
    except Exception as e:
        sys.exit(f"ERROR: Failed to fetch webpage: {e}")

    pattern = r'<option\s+[^>]*value="([^"]+)"[^>]*>([^<]+)</option>'
    matches = re.findall(pattern, html_content)

    target_init_time = None
    for val, label in matches:
        if not INCLUDE_ECMWF and "ECMWF" in label:
            continue
            
        target_init_time = val
        print(f"Found target initial time (INCLUDE_ECMWF={INCLUDE_ECMWF}): {val} ({label.strip()})")
        break

    if not target_init_time:
        sys.exit("ERROR: No valid initial time found matching the specified criteria.")

    initial_dir = "initial"
    os.makedirs(initial_dir, exist_ok=True)

    filename = f"p1h.d02.{target_init_time}.csv"
    file_url = f"https://hpc.tmd.go.th/static/csv/{target_init_time}/{filename}"
    save_path = os.path.join(initial_dir, filename)

    # ---------------------------------------------------------
    # ตรวจสอบขนาดไฟล์บน Server (HTTP HEAD Request)
    # ---------------------------------------------------------
    server_file_size = None
    try:
        head_req = urllib.request.Request(file_url, headers=headers, method="HEAD")
        with urllib.request.urlopen(head_req) as head_res:
            content_length = head_res.getheader("Content-Length")
            if content_length:
                server_file_size = int(content_length)
    except Exception as e:
        print(f"Warning: Could not fetch header info from server ({e}). Will proceed normally.")

    # ตรวจสอบว่ามีไฟล์เดิมอยู่แล้ว และขนาดตรงกันหรือไม่
    if os.path.exists(save_path):
        local_file_size = os.path.getsize(save_path)
        if server_file_size is not None and local_file_size == server_file_size:
            print(f"Local file exists and matches server size ({local_file_size / (1024*1024):.2f} MB). Skipping download.\n")
            return save_path
        elif server_file_size is None and local_file_size > 0:
            print(f"Local file exists ({local_file_size / (1024*1024):.2f} MB). Skipping download.\n")
            return save_path

    # ---------------------------------------------------------
    # ดาวน์โหลดไฟล์ใหม่หากยังไม่มี หรือขนาดไม่ตรงกัน
    # ---------------------------------------------------------
    print(f"Downloading CSV from: {file_url}")
    try:
        file_req = urllib.request.Request(file_url, headers=headers)
        with urllib.request.urlopen(file_req) as response, open(save_path, "wb") as f:
            total_size = response.getheader("Content-Length")
            total_bytes = int(total_size) if total_size else server_file_size
            
            downloaded = 0
            chunk_size = 1024 * 64
            
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                
                if total_bytes:
                    percent = downloaded / total_bytes * 100
                    mb_downloaded = downloaded / (1024 * 1024)
                    mb_total = total_bytes / (1024 * 1024)
                    bar = '#' * int(percent // 2) + '-' * (50 - int(percent // 2))
                    sys.stdout.write(f"\r[{bar}] {percent:5.1f}% ({mb_downloaded:.2f}/{mb_total:.2f} MB)")
                else:
                    mb_downloaded = downloaded / (1024 * 1024)
                    sys.stdout.write(f"\rDownloaded: {mb_downloaded:.2f} MB")
                sys.stdout.flush()

        print(f"\nDownloaded and saved to: {save_path}\n")
    except Exception as e:
        sys.exit(f"\nERROR: Failed to download CSV file: {e}")

    return save_path


# ==========================================
# 2. INTERPOLATION & CROP MODULE
# ==========================================
def load_vertices(xlsx_path):
    """Read all vertex points (degrees WGS84) from the 'Vertices' sheet."""
    if not os.path.exists(xlsx_path):
        sys.exit(f"ERROR: Template file '{xlsx_path}' not found.")

    df = pd.read_excel(xlsx_path, sheet_name="Vertices")
    lon_col = [c for c in df.columns if "ongitude" in str(c)][0]
    lat_col = [c for c in df.columns if "atitude" in str(c)][0]
    vcol = [c for c in df.columns if "ertex" in str(c)]
    v = df[vcol[0]].astype(int) if vcol else pd.Series(range(1, len(df) + 1))
    return v.tolist(), df[lon_col].astype(float).values, df[lat_col].astype(float).values


def make_interpolator(method, gx, gy, px, py):
    """Build a callable values(n_grid,) -> (n_pts,) for the given method."""
    pts = np.column_stack([px, py])
    grid_pts = np.column_stack([gx, gy])
    tree = cKDTree(grid_pts)
    dist, idx = tree.query(pts, k=1)

    if method == "nearest":
        return lambda v: (v[idx], idx)

    if method == "lerp":
        _, k2 = tree.query(grid_pts[:200], k=2)
        nn = np.linalg.norm(grid_pts[k2] - grid_pts[:200, None], axis=2)
        spacing = np.median(nn[:, 1])
        x0, y0 = gx.min(), gy.min()
        nx = int(round((gx.max() - x0) / spacing)) + 1
        ny = int(round((gy.max() - y0) / spacing)) + 1
        ix = np.round((gx - x0) / spacing).astype(int)
        iy = np.round((gy - y0) / spacing).astype(int)
        ok = (
            nx * ny < 50_000_000
            and np.unique(iy * nx + ix).size == len(gx)
            and (ix >= 0).all() and (ix < nx).all() and (iy >= 0).all() and (iy < ny).all()
        )
        if ok:
            xg = x0 + np.arange(nx) * spacing
            yg = y0 + np.arange(ny) * spacing

            def lerp(v):
                grid = np.full((ny, nx), np.nan)
                grid[iy, ix] = v
                f = RegularGridInterpolator(
                    (yg, xg), grid, method="linear", bounds_error=False, fill_value=np.nan
                )
                out = f(pts)
                nan = np.isnan(out)
                if nan.any():
                    out[nan] = v[idx[nan]]
                return out, idx

            return lerp
        print("Note: grid is not regular, 'lerp' falls back to triangulated linear")
        method = "linear"

    if method in ("linear", "cubic"):
        tri = Delaunay(grid_pts)
        interp_cls = LinearNDInterpolator if method == "linear" else CloughTocher2DInterpolator

        def tri_interp(v):
            out = interp_cls(tri, v)(pts)
            nan = np.isnan(out)
            if nan.any():
                out[nan] = v[idx[nan]]
            return out, idx

        return tri_interp

    if method == "idw":
        d, i = tree.query(pts, k=min(IDW_NEIGHBORS, len(gx)))
        if d.ndim == 1:
            d, i = d[:, None], i[:, None]
        w = 1.0 / np.maximum(d, 1e-9) ** 2
        w /= w.sum(axis=1, keepdims=True)
        return lambda v: ((v[i] * w).sum(axis=1), idx)

    if method == "kriging":
        k = min(16, len(gx))
        d, i = tree.query(pts, k=k)
        if d.ndim == 1:
            d, i = d[:, None], i[:, None]
        nb_x = gx[i][:, :, None]
        nb_y = gy[i][:, :, None]
        
        _, k2 = tree.query(np.column_stack([gx, gy])[:200], k=2)
        spacing = np.median(
            np.linalg.norm(np.column_stack([gx, gy])[k2] - np.column_stack([gx, gy])[:200, None], axis=2)[:, 1]
        )
        a = 3.0 * spacing

        def gamma(dist):
            r = np.minimum(dist / a, 1.0)
            return 1.5 * r - 0.5 * r**3

        dd = np.sqrt((nb_x - nb_x.transpose(0, 2, 1)) ** 2 + (nb_y - nb_y.transpose(0, 2, 1)) ** 2)
        A = np.ones((len(pts), k + 1, k + 1))
        A[:, :k, :k] = gamma(dd)
        A[:, k, k] = 0.0
        rhs_dist = np.sqrt((px[:, None] - gx[i]) ** 2 + (py[:, None] - gy[i]) ** 2)
        rhs = np.ones((len(pts), k + 1))
        rhs[:, :k] = gamma(rhs_dist)
        weights = np.linalg.solve(A, rhs[:, :, None])[:, :k, 0]

        return lambda v: (np.maximum((v[i] * weights).sum(axis=1), 0.0), idx)

    sys.exit(f"ERROR: Unknown interpolation method: {method}")


def resolve_template_path(template_path):
    """Resolve the template path and tolerate DA_X44 <-> DA_X_44 naming."""
    candidates = [template_path]

    dirname = os.path.dirname(template_path)
    basename = os.path.basename(template_path)

    # DA_X44... -> DA_X_44...
    m = re.match(r"^(DA_X)(\d+)(.*)$", basename, flags=re.IGNORECASE)
    if m:
        candidates.append(os.path.join(dirname, f"{m.group(1)}_{m.group(2)}{m.group(3)}"))

    # DA_X_44... -> DA_X44...
    m = re.match(r"^(DA_X)_(\d+)(.*)$", basename, flags=re.IGNORECASE)
    if m:
        candidates.append(os.path.join(dirname, f"{m.group(1)}{m.group(2)}{m.group(3)}"))

    # Also check relative paths from the script directory.
    script_dir = os.path.dirname(os.path.abspath(__file__))
    expanded = []
    for candidate in candidates:
        expanded.append(candidate)
        if not os.path.isabs(candidate):
            expanded.append(os.path.join(script_dir, candidate))

    seen = set()
    for candidate in expanded:
        normalized = os.path.normpath(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        if os.path.isfile(normalized):
            return normalized

    checked = "\n  - ".join(seen)
    sys.exit(
        f"ERROR: Template file '{template_path}' not found.\n"
        f"Checked:\n  - {checked}"
    )


def process_crop(csv_input_path, template_path, output_path, method):
    """Run extraction and interpolation on the downloaded CSV."""
    print(f"[2/2] Processing Crop with Method: '{method}' ...")
    t0 = time.time()

    df = pd.read_csv(csv_input_path)
    time_cols = [c for c in df.columns if c not in ("lat", "lon")]

    transformer = Transformer.from_crs(4326, UTM_EPSG, always_xy=True)

    raw_lat = df["lat"].to_numpy(float)
    raw_lon = df["lon"].to_numpy(float)

    if np.abs(raw_lat).max() <= 360 and np.abs(raw_lon).max() <= 360:
        gx, gy = transformer.transform(raw_lon, raw_lat)
    else:
        gx, gy = raw_lon, raw_lat

    gvals = df[time_cols].to_numpy(float)

    vids, vlon, vlat = load_vertices(template_path)
    px, py = transformer.transform(vlon, vlat)

    interp = make_interpolator(method, gx, gy, px, py)
    out_vals = np.empty((len(vids), len(time_cols)))
    nearest_idx = None

    for j, col in enumerate(time_cols):
        out_vals[:, j], nearest_idx = interp(gvals[:, j])

    out = pd.DataFrame(
        {
            "Vertex": vids,
            "Longitude": vlon,
            "Latitude": vlat,
            "dist_m": np.hypot(px - gx[nearest_idx], py - gy[nearest_idx]),
            "grid_lat": raw_lat[nearest_idx],
            "grid_lon": raw_lon[nearest_idx],
        }
    )
    out[time_cols] = out_vals

    da_name = os.path.basename(template_path).split("_boundary")[0]
    out_name = f"{da_name}_{os.path.basename(csv_input_path)}"
    
    if method != "kriging":
        base, ext = os.path.splitext(out_name)
        out_name = f"{base}_{method}{ext}"

    if os.path.isdir(output_path) or not output_path.lower().endswith(".csv"):
        os.makedirs(output_path, exist_ok=True)
        final_out_path = os.path.join(output_path, out_name)
    else:
        final_out_path = output_path
        parent = os.path.dirname(os.path.abspath(final_out_path))
        os.makedirs(parent, exist_ok=True)

    out.to_csv(final_out_path, index=False)

    print("-" * 50)
    print(f"Method             : {method}")
    print(f"Vertices           : {len(vids)}")
    print(f"Grid points        : {len(df)}")
    print(f"Elapsed            : {time.time() - t0:.2f} s")
    print(f"Saved Output To    : {final_out_path}")
    print("-" * 50)


# ==========================================
# MAIN EXECUTION
# ==========================================
# ==========================================
# MAIN EXECUTION - BATCH MULTIPLE BOUNDARIES
# ==========================================
BATCH_JOBS = [
    ("DA_X_44_boundary_coordinates.xlsx",  "X44.csv"),
    ("DA_X_71B_boundary_coordinates.xlsx", "X71B.csv"),
    ("DA_X_90_boundary_coordinates.xlsx",  "X90.csv"),
    ("DA_X_174_boundary_coordinates.xlsx", "X174.csv"),
    ("DA_X_240_boundary_coordinates.xlsx", "X240.csv"),
]

def parse_args():
    ap = argparse.ArgumentParser(
        description="Download/use one NWP CSV and process all configured DA boundaries in one command."
    )
    ap.add_argument(
        "-i", "--input",
        help="Input NWP CSV. If omitted, download the latest CSV automatically.",
    )
    ap.add_argument(
        "-o", "--output-dir",
        default="result",
        help="Output directory for X44.csv, X71B.csv, X90.csv, X174.csv, X240.csv (default: result)",
    )
    ap.add_argument(
        "-m", "--method",
        default=DEFAULT_METHOD,
        choices=["nearest", "lerp", "linear", "cubic", "idw", "kriging"],
        help=f"Interpolation method for all boundaries (default: {DEFAULT_METHOD})",
    )
    ap.add_argument(
        "--download-latest",
        action="store_true",
        help="Ignore -i and download the latest available NWP CSV.",
    )
    return ap.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.download_latest or not args.input:
        csv_input_path = fetch_and_download_latest_nwp()
    else:
        csv_input_path = os.path.normpath(args.input)
        if not os.path.isfile(csv_input_path):
            script_candidate = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), csv_input_path
            )
            if os.path.isfile(script_candidate):
                csv_input_path = script_candidate
            else:
                sys.exit(f"ERROR: Input CSV file '{args.input}' not found.")
        print(f"[1/2] Using local CSV: {csv_input_path}\n")

    output_dir = os.path.normpath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print(f"Input CSV            : {csv_input_path}")
    print(f"Output directory     : {output_dir}")
    print(f"Interpolation method : {args.method}")
    print(f"Boundary jobs        : {len(BATCH_JOBS)}")
    print("=" * 60)

    failed = []
    for n, (template_name, output_name) in enumerate(BATCH_JOBS, 1):
        print(f"\n[{n}/{len(BATCH_JOBS)}] {template_name} -> {output_name}")
        try:
            template_path = resolve_template_path(template_name)
            output_path = os.path.join(output_dir, output_name)
            process_crop(
                csv_input_path=csv_input_path,
                template_path=template_path,
                output_path=output_path,
                method=args.method,
            )
        except SystemExit as e:
            failed.append((template_name, str(e)))
            print(f"FAILED: {e}")
        except Exception as e:
            failed.append((template_name, str(e)))
            print(f"FAILED: {e}")

    print("\n" + "=" * 60)
    if failed:
        print(f"Completed with {len(failed)} failed job(s):")
        for template_name, err in failed:
            print(f"  - {template_name}: {err}")
        sys.exit(1)
    else:
        print("SUCCESS: All 5 boundary files processed.")
        print("Outputs:")
        for _, output_name in BATCH_JOBS:
            print(f"  - {os.path.join(output_dir, output_name)}")
    print("=" * 60)

MODDIR=${0%/*}
. "$MODDIR/common.sh"

# Keep the blocking boot stage free of package-manager calls and app-data scans.
mount_oem_fonts

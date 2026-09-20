# Placeholder pipeline — phản hồi review kỹ thuật (P0/P1)

Tài liệu này ghi lại các sửa đổi sau bản review chi tiết về `base_mesh_placeholder.glb` và
bộ script Blender. Nguyên tắc: sửa dứt điểm các lỗi đúng nghĩa (P0), thêm các lớp kiểm tra tự
động (P1), và **ghi rõ ràng những gì vẫn là placeholder chứ không phải production** thay vì để
kết quả bị hiểu nhầm là asset tin cậy.

## Đã sửa — P0

### 1. Bone hierarchy snap sai (`use_connect`)
`build_armature` trước đây đặt `use_connect=True` cho **mọi** cặp parent-child, kể cả nhánh
`chest→shoulder` và `hips→thigh`. Vì tail của `chest` nằm ở `neck` và tail của `hips` nằm ở
`spine`, việc connect làm head của vai/đùi bị hút về centerline — sai giải phẫu.

**Sửa:** thêm `BRANCH_EDGES` và chỉ connect các chain liên tục
(`hips→spine→chest→neck→head`, `shoulder→upper_arm→forearm→hand`,
`thigh→shin→foot→toe`). Nhánh vai/đùi parent nhưng **không** connect.

**Bằng chứng (đọc lại từ GLB, không phải tin exporter):** bind-pose world position của
`upper_arm.L` = x≈0.173 (đúng khớp vai), `thigh.L` = x≈0.091 (đúng khớp hông). Nếu còn bug,
hai giá trị này sẽ ≈0. Validator có check `shoulder_not_snapped` / `thigh_not_snapped`.

### 2. Bone naming theo spec
Đổi `elbow/knee/ankle` → chain đúng spec section 5: `upper_arm`, `forearm`, `shin`, `foot`,
và thêm bone `shoulder` (clavicle) tách khỏi `upper_arm`. Toàn bộ shape-key reference
(`torso_limbs`, `arm_mass`, `leg_mass`) cập nhật theo. Validator có `joint_names_spec` kiểm tra
đủ 20 bone tên chuẩn (10 mỗi bên).

### 3. Bounds sai 1.75 m + xuyên đất
Skin radius làm envelope vượt joint. Thêm `normalize_to_height()`: đo envelope thật (sau
subsurf), scale + offset đồng nhất cả mesh (mọi shape key) lẫn armature để **min-Z=0, cao đúng
1.75 m**, rồi mới skin (auto-weight tính trên geometry đã chuẩn hoá). Xuất
`base_mesh_placeholder_bounds_report.json` với bounds trước/sau.

**Bằng chứng (đọc accessor GLB Y-up):** height=1.7500 m, min_Y=0.0000. Trước đó envelope cao
~1.858 m và xuyên đất ~13 cm.

### 4. Height morph giữ chân trên đất
`legwise_stretch` (đẩy chân xuống → bàn chân dưới ground) thay bằng `height_offset`: scale toàn
thân quanh pivot Z=0, nên vertex ở z=0 (bàn chân) không di chuyển ở mọi giá trị morph.

**Bằng chứng (đo trên GLB xuất ra):**
| morph | min_Z | cao |
|---|---|---|
| neutral | 0.0000 | 1.750 m |
| height_tall=1.0 | +0.0002 | 1.855 m |
| height_short=1.0 | −0.0002 | 1.645 m |
| tall+muscle 0.8+fat 0.6 | +0.0002 | 1.868 m |

Bàn chân giữ ở z≈0 ở mọi mức, trong khi chiều cao thay đổi đúng hướng.

### 5. C/D cô lập biến khuôn mặt (v1.1)
C và D trước đây khác `body_fat` (0.45 vs 0.50) → không thật sự "face-only". Nay **body params
giống hệt nhau**, chỉ khác `face_width`/`eye_spacing`/`eye_angle`. Thêm `assert_face_only_pair()`
**fail trước khi render** nếu body param lệch, và xuất `v1_1_manifest.json` + in diff.

## Đã thêm — P1

- **`tools/blender/validate_glb.py`** — QA sau export, parse GLB thuần Python (chạy mọi nơi,
  không cần Blender): bounds/ground/Y-up, skin attributes, weight-sum ~1, max 4 influences,
  UV/material, 18 morph name, 20 joint name, 3 animation clip, và bind-pose joint position để
  bắt bug snap. Exit code ≠0 nếu fail check bắt buộc → gắn được vào CI. Kết quả hiện tại: mọi
  check bắt buộc PASS; UV là WARN (placeholder không có UV — đúng như dự kiến).
- **Rig verification bằng số** thay cho ảnh overlay: bones không phải geometry nên không render
  headless được; bind-pose world position đọc từ inverse-bind-matrix là bằng chứng mạnh hơn ảnh.
- **Height morph ground-contact check** (bảng trên) chạy trên GLB thật.
- **Pillow ImportError fallback** trong `label_image`: thiếu Pillow thì vẫn render ảnh không
  nhãn + in cảnh báo, không crash.
- **Watermark `DEBUG LANDMARKS - NOT FACIAL VALIDATION`** trên mọi ảnh profile (marker mắt tách
  khỏi silhouette đầu ở góc nghiêng — chỉ để debug, không phải validation khuôn mặt).

## KHÔNG sửa — vẫn là placeholder, không phải production (ghi rõ để tránh hiểu nhầm)

Đúng như review B1 nhấn mạnh: mesh này sinh từ Skin modifier → **topology dạng capsule/tube**,
KHÔNG phải topology nhân vật. Vì vậy **không dùng nó để kết luận** về:
- facial identity / facial blend shape (không có edge flow mắt/miệng/hàm),
- skin deformation chất lượng, clothing fit, animation deformation thật,
- chất lượng model cuối.

Nó chỉ hợp lệ để kiểm tra **pipeline** (đọc morph theo tên, rig hierarchy, bounds, animation
clip, export GLB). Các morph mặt (`nose_wide`, `eyes_wide_set`...) hiện chỉ là **approximate
deformation trên khối đầu trơn** — khi có base mesh mặt thật phải rebuild theo topology thật.

## Chưa làm — P2 và phần chặn bởi base mesh thật

- Schema/validation đầy đủ cho character profile (mới có assert cho cặp C/D).
- Weight QA report chi tiết (max influences per vertex, zero-weight vertex, pose test xoay
  vai/hông) — validator hiện chỉ kiểm max-4 + weight-sum ở mức GLB.
- Shape-key intermediate contact sheet (render 0.25/0.5/0.75/1.0 + self-intersection/normal
  flip check) — review E3.
- QA render có ground plane/grid/origin/ruler tách khỏi ảnh art.
- Chế độ render ẩn danh (bỏ nhãn) cho blind test.
- UV/texture/topology mặt thật — **chặn bởi bàn giao của hoạ sĩ**, không làm được ở phía app.

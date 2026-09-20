# Thiết kế hệ thống nhân vật 3D

Khung code trong `src/character/` hiện thực phần app-side của
[`character-spec.md`](./character-spec.md): nhận file `.glb` do hoạ sĩ giao, và điều khiển
blend shapes bằng dữ liệu người dùng thật (tập luyện, cân nặng/chiều cao, face scan).

## Lựa chọn công nghệ

- **react-three-fiber (`@react-three/fiber/native`) + `@react-three/drei/native`** trên nền
  `expo-gl`, thay vì gọi three.js thuần. Spec chỉ định three.js làm renderer; r3f là lớp khai
  báo phổ biến nhất cho three.js trong React Native, giữ nguyên toàn bộ API three.js bên
  dưới (morph targets, `AnimationMixer`, material) nên không đánh đổi khả năng kiểm soát.
- Toàn bộ logic map dữ liệu → blend shape (`blendShapeMapping.ts`) là hàm thuần, không phụ
  thuộc React hay three.js, để test được độc lập và tái dùng nếu sau này đổi renderer.

## Luồng dữ liệu

```
UserCharacterStats (workout, body, face)
        │  computeBlendShapeValues()
        ▼
BlendShapeValues { [blendShapeName]: 0..1 }
        │  useBlendShapes() — mỗi frame, lerp về giá trị mới
        ▼
mesh.morphTargetInfluences[index]  (base mesh + từng món trang phục)
```

`useBlendShapes` không snap thẳng giá trị mới vào `morphTargetInfluences` — nó lerp theo
thời gian mỗi frame (`LERP_SPEED` trong `useBlendShapes.ts`). Lý do: dữ liệu người dùng
(cân nặng, khối lượng tập) chỉ cập nhật theo đợt (sau khi sync), nếu áp thẳng sẽ làm nhân
vật "giật" hình thể ngay khi mở app thay vì cảm giác thay đổi dần — đúng tinh thần "biến đổi
diễn ra dần qua nhiều tuần" ở mục 1 của spec.

## Vì sao tách `blendShapeMapping.ts` khỏi hook render

Việc map dữ liệu thật (ví dụ tỉ lệ mỡ 0..1) sang giá trị blend shape có quy tắc riêng — quan
trọng nhất là ràng buộc **cặp đối lập loại trừ lẫn nhau** (mục 4/4c của spec:
`body_fat`/`body_thin`, `height_tall`/`height_short`, và bốn cặp ở mục 4b). `splitSigned()`
mã hoá đúng quy tắc này: một tỉ lệ 0..1 quanh điểm giữa 0.5 chỉ có thể đẩy MỘT bên của cặp
lên khác 0, `assertMutuallyExclusivePairs()` là lớp bảo vệ cuối cùng phòng khi input tính sai.
Đây là chỗ nhiều khả năng cần điều chỉnh công thức khi có dữ liệu thật từ backend — nên nó
độc lập khỏi phần render.

## Đồng bộ trang phục với thân người (mục 6)

`CharacterViewer` không coi trang phục là texture hay child mesh gắn cứng vào base mesh —
mỗi món trang phục (`ClothingItemDef`) là một `.glb` riêng, được load và áp **cùng một
`blendShapeValues`** như base mesh. Vì hoạ sĩ giao trang phục với bộ blend shape trùng tên
(yêu cầu bắt buộc của spec), khi `body_muscle` tăng thì cả người lẫn áo cùng morph theo,
không cần logic đặc biệt nào trong app để "co giãn" quần áo.

`BODY_PART_GROUPS` trong `constants.ts` phản ánh yêu cầu ẩn phần thân bị che (mục 6) —
hiện là danh sách tên group để lớp ẩn/hiện mesh dùng sau này; logic ẩn theo `covers` của
từng `ClothingItemDef` chưa viết vì phụ thuộc cách hoạ sĩ đặt tên group trong file `.glb` thật,
sẽ hoàn thiện khi có file mẫu đầu tiên.

## Nhuộm màu da/trang phục bằng shader (mục 7)

`applyTint()` nhân màu trực tiếp lên `material.color` thay vì đổi texture, khớp với yêu cầu
"ứng dụng sẽ nhuộm màu da theo lựa chọn của người dùng bằng cách nhân màu trong shader".
Hàm này match material theo tên (`material.name` chứa "skin" hoặc "clothing") — quy ước đặt
tên material chính xác cần chốt với hoạ sĩ khi duyệt base mesh (đợt thanh toán thứ hai, mục
8), vì hiện chưa có file thật để biết tên material họ dùng.

## Animation (mục 5)

`AnimationController` bọc `THREE.AnimationMixer`, chỉ nhận diện ba tên clip trong
`ANIMATION_CLIPS` (`idle`, `celebrate`, `showcase`). `celebrate` được set `LoopOnce` và tự
động chuyển về lại `idle` khi phát xong, đúng mô tả "ăn mừng khi lên level" rồi trở lại trạng
thái đứng yên trên màn hình chính.

## Việc còn để trống, chờ asset thật

- `assets/characters/` hiện trống — `App.tsx` cố tình để `BASE_MESH_URI = null` và hiện màn
  hình chờ, để tránh Metro bundler crash vì `require()` một file không tồn tại.
- Chưa viết test cho `computeBlendShapeValues` — nên thêm khi chốt công thức map thật với
  team dữ liệu (hiện các hệ số trong `blendShapeMapping.ts`, ví dụ dải ±30cm cho chiều cao,
  là giá trị giả định cần xác nhận lại).
- Chưa có logic ẩn body-part theo trang phục (xem mục "Đồng bộ trang phục" ở trên).

"""Word lists for synthetic data. Every generated value is random and fictional.

Ward and street names only need a realistic *format*; they are illustrative
and must not be treated as an official list of administrative units.
"""

from __future__ import annotations

SURNAMES = (
    "Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Huỳnh", "Phan", "Vũ", "Võ", "Đặng",
    "Bùi", "Đỗ", "Hồ", "Ngô", "Dương", "Lý", "Đinh", "Trương", "Lâm", "Mai",
)  # fmt: skip
MIDDLE_MALE = ("Văn", "Hữu", "Đức", "Minh", "Quốc", "Thanh", "Gia", "Hoàng", "Công", "Tuấn")
MIDDLE_FEMALE = ("Thị", "Ngọc", "Thanh", "Thu", "Minh", "Bảo", "Kim", "Phương", "Hồng", "Mỹ")
GIVEN_MALE = (
    "An", "Bình", "Cường", "Dũng", "Đạt", "Hải", "Hiếu", "Hùng", "Khánh", "Long",
    "Nam", "Phúc", "Quân", "Sơn", "Tâm", "Thắng", "Trung", "Tuấn", "Việt", "Vinh",
)  # fmt: skip
GIVEN_FEMALE = (
    "Anh", "Châu", "Hà", "Hạnh", "Hoa", "Hương", "Lan", "Linh", "Mai", "Nga",
    "Ngân", "Nhung", "Quyên", "Thảo", "Trang", "Uyên", "Vy", "Yến", "Diệp", "Như",
)  # fmt: skip

STREETS = (
    "Lê Lợi", "Nguyễn Huệ", "Trần Hưng Đạo", "Hai Bà Trưng", "Lý Thường Kiệt",
    "Nguyễn Trãi", "Cách Mạng Tháng Tám", "Võ Văn Tần", "Phan Đình Phùng", "Lê Duẩn",
    "Nguyễn Văn Linh", "Quang Trung", "Hoàng Diệu", "Bạch Đằng", "Pasteur",
)  # fmt: skip

# Two-level format used since 1 July 2025: ward/commune + province/city.
WARDS_POST_2025 = (
    ("phường Bến Thành", "TP. Hồ Chí Minh"),
    ("phường Sài Gòn", "TP. Hồ Chí Minh"),
    ("phường Tân Định", "TP. Hồ Chí Minh"),
    ("phường Bình Thạnh", "TP. Hồ Chí Minh"),
    ("phường Thủ Đức", "TP. Hồ Chí Minh"),
    ("phường Hoàn Kiếm", "TP. Hà Nội"),
    ("phường Ba Đình", "TP. Hà Nội"),
    ("phường Cửa Nam", "TP. Hà Nội"),
    ("phường Hải Châu", "TP. Đà Nẵng"),
    ("xã Bình Chánh", "TP. Hồ Chí Minh"),
)
# Three-level format used before July 2025: ward + district + province.
WARDS_PRE_2025 = (
    ("phường Bến Nghé", "quận 1", "TP. Hồ Chí Minh"),
    ("phường 6", "quận 3", "TP.HCM"),
    ("phường Đa Kao", "quận 1", "TP. Hồ Chí Minh"),
    ("phường Linh Trung", "TP. Thủ Đức", "TP. Hồ Chí Minh"),
    ("phường Hàng Trống", "quận Hoàn Kiếm", "Hà Nội"),
    ("phường Điện Biên", "quận Ba Đình", "Hà Nội"),
    ("phường Thạch Thang", "quận Hải Châu", "Đà Nẵng"),
    ("xã Tân Thông Hội", "huyện Củ Chi", "TP. Hồ Chí Minh"),
)

BANKS = ("Vietcombank", "Techcombank", "BIDV", "VietinBank", "MB Bank", "ACB", "VPBank", "TPBank")
EMAIL_DOMAINS = ("gmail.com", "yahoo.com.vn", "outlook.com", "icloud.com", "example.vn")
PASSPORT_LETTERS = ("B", "C", "K", "N", "P")
PLATE_SERIES_CAR = ("A", "F", "G", "H", "K", "LD")
PLATE_SERIES_BIKE = ("B1", "F1", "H1", "K1", "X1", "C2", "G1")

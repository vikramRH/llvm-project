; NOTE: Assertions have been autogenerated by utils/update_test_checks.py
; Test that the strlen library call simplifier works correctly.
;
; RUN: opt < %s -passes=instcombine -S | FileCheck %s

target datalayout = "e-p:32:32:32-i1:8:8-i8:8:8-i16:16:16-i32:32:32-i64:32:64-f32:32:32-f64:32:64-v64:64:64-v128:128:128-a0:0:64-f80:128:128"

@hello = constant [6 x i8] c"hello\00"
@longer = constant [7 x i8] c"longer\00"
@null = constant [1 x i8] zeroinitializer
@null_hello = constant [7 x i8] c"\00hello\00"
@nullstring = constant i8 0
@a = common global [32 x i8] zeroinitializer, align 1
@null_hello_mid = constant [13 x i8] c"hello wor\00ld\00"

declare i32 @strlen(ptr)

; Check strlen(string constant) -> integer constant.

define i32 @test_simplify1() {
; CHECK-LABEL: @test_simplify1(
; CHECK-NEXT:    ret i32 5
;
  %hello_l = call i32 @strlen(ptr @hello)
  ret i32 %hello_l
}

define i32 @test_simplify2() {
; CHECK-LABEL: @test_simplify2(
; CHECK-NEXT:    ret i32 0
;
  %null_l = call i32 @strlen(ptr @null)
  ret i32 %null_l
}

define i32 @test_simplify3() {
; CHECK-LABEL: @test_simplify3(
; CHECK-NEXT:    ret i32 0
;
  %null_hello_l = call i32 @strlen(ptr @null_hello)
  ret i32 %null_hello_l
}

define i32 @test_simplify4() {
; CHECK-LABEL: @test_simplify4(
; CHECK-NEXT:    ret i32 0
;
  %len = tail call i32 @strlen(ptr @nullstring) nounwind
  ret i32 %len
}

; Check strlen(x) == 0 --> *x == 0.

define i1 @test_simplify5() {
; CHECK-LABEL: @test_simplify5(
; CHECK-NEXT:    ret i1 false
;
  %hello_l = call i32 @strlen(ptr @hello)
  %eq_hello = icmp eq i32 %hello_l, 0
  ret i1 %eq_hello
}

define i1 @test_simplify6(ptr %str_p) {
; CHECK-LABEL: @test_simplify6(
; CHECK-NEXT:    [[CHAR0:%.*]] = load i8, ptr [[STR_P:%.*]], align 1
; CHECK-NEXT:    [[EQ_NULL:%.*]] = icmp eq i8 [[CHAR0]], 0
; CHECK-NEXT:    ret i1 [[EQ_NULL]]
;
  %str_l = call i32 @strlen(ptr %str_p)
  %eq_null = icmp eq i32 %str_l, 0
  ret i1 %eq_null
}

; Check strlen(x) != 0 --> *x != 0.

define i1 @test_simplify7() {
; CHECK-LABEL: @test_simplify7(
; CHECK-NEXT:    ret i1 true
;
  %hello_l = call i32 @strlen(ptr @hello)
  %ne_hello = icmp ne i32 %hello_l, 0
  ret i1 %ne_hello
}

define i1 @test_simplify8(ptr %str_p) {
; CHECK-LABEL: @test_simplify8(
; CHECK-NEXT:    [[CHAR0:%.*]] = load i8, ptr [[STR_P:%.*]], align 1
; CHECK-NEXT:    [[NE_NULL:%.*]] = icmp ne i8 [[CHAR0]], 0
; CHECK-NEXT:    ret i1 [[NE_NULL]]
;
  %str_l = call i32 @strlen(ptr %str_p)
  %ne_null = icmp ne i32 %str_l, 0
  ret i1 %ne_null
}

define i32 @test_simplify9(i1 %x) {
; CHECK-LABEL: @test_simplify9(
; CHECK-NEXT:    [[L:%.*]] = select i1 [[X:%.*]], i32 5, i32 6
; CHECK-NEXT:    ret i32 [[L]]
;
  %s = select i1 %x, ptr @hello, ptr @longer
  %l = call i32 @strlen(ptr %s)
  ret i32 %l
}

; Check the case that should be simplified to a sub instruction.
; strlen(@hello + x) --> 5 - x

define i32 @test_simplify10_inbounds(i32 %x) {
; CHECK-LABEL: @test_simplify10_inbounds(
; CHECK-NEXT:    [[HELLO_L:%.*]] = sub i32 5, [[X:%.*]]
; CHECK-NEXT:    ret i32 [[HELLO_L]]
;
  %hello_p = getelementptr inbounds [6 x i8], ptr @hello, i32 0, i32 %x
  %hello_l = call i32 @strlen(ptr %hello_p)
  ret i32 %hello_l
}

define i32 @test_simplify10_no_inbounds(i32 %x) {
; CHECK-LABEL: @test_simplify10_no_inbounds(
; CHECK-NEXT:    [[HELLO_L:%.*]] = sub i32 5, [[X:%.*]]
; CHECK-NEXT:    ret i32 [[HELLO_L]]
;
  %hello_p = getelementptr [6 x i8], ptr @hello, i32 0, i32 %x
  %hello_l = call i32 @strlen(ptr %hello_p)
  ret i32 %hello_l
}

; strlen(@null_hello_mid + (x & 7)) --> 9 - (x & 7)

define i32 @test_simplify11(i32 %x) {
; CHECK-LABEL: @test_simplify11(
; CHECK-NEXT:    [[AND:%.*]] = and i32 [[X:%.*]], 7
; CHECK-NEXT:    [[HELLO_L:%.*]] = sub nuw nsw i32 9, [[AND]]
; CHECK-NEXT:    ret i32 [[HELLO_L]]
;
  %and = and i32 %x, 7
  %hello_p = getelementptr inbounds [13 x i8], ptr @null_hello_mid, i32 0, i32 %and
  %hello_l = call i32 @strlen(ptr %hello_p)
  ret i32 %hello_l
}

; Check cases that shouldn't be simplified.

define i32 @test_no_simplify1() {
; CHECK-LABEL: @test_no_simplify1(
; CHECK-NEXT:    [[A_L:%.*]] = call i32 @strlen(ptr noundef nonnull dereferenceable(1) @a)
; CHECK-NEXT:    ret i32 [[A_L]]
;
  %a_l = call i32 @strlen(ptr @a)
  ret i32 %a_l
}

; strlen(@null_hello + x) should not be simplified to a sub instruction.

define i32 @test_no_simplify2(i32 %x) {
; CHECK-LABEL: @test_no_simplify2(
; CHECK-NEXT:    [[HELLO_P:%.*]] = getelementptr inbounds [7 x i8], ptr @null_hello, i32 0, i32 [[X:%.*]]
; CHECK-NEXT:    [[HELLO_L:%.*]] = call i32 @strlen(ptr noundef nonnull dereferenceable(1) [[HELLO_P]])
; CHECK-NEXT:    ret i32 [[HELLO_L]]
;
  %hello_p = getelementptr inbounds [7 x i8], ptr @null_hello, i32 0, i32 %x
  %hello_l = call i32 @strlen(ptr %hello_p)
  ret i32 %hello_l
}

define i32 @test_no_simplify2_no_null_opt(i32 %x) #0 {
; CHECK-LABEL: @test_no_simplify2_no_null_opt(
; CHECK-NEXT:    [[HELLO_P:%.*]] = getelementptr inbounds [7 x i8], ptr @null_hello, i32 0, i32 [[X:%.*]]
; CHECK-NEXT:    [[HELLO_L:%.*]] = call i32 @strlen(ptr noundef [[HELLO_P]])
; CHECK-NEXT:    ret i32 [[HELLO_L]]
;
  %hello_p = getelementptr inbounds [7 x i8], ptr @null_hello, i32 0, i32 %x
  %hello_l = call i32 @strlen(ptr %hello_p)
  ret i32 %hello_l
}

; strlen(@null_hello_mid + (x & 15)) should not be simplified to a sub instruction.

define i32 @test_no_simplify3(i32 %x) {
; CHECK-LABEL: @test_no_simplify3(
; CHECK-NEXT:    [[AND:%.*]] = and i32 [[X:%.*]], 15
; CHECK-NEXT:    [[HELLO_P:%.*]] = getelementptr inbounds nuw [13 x i8], ptr @null_hello_mid, i32 0, i32 [[AND]]
; CHECK-NEXT:    [[HELLO_L:%.*]] = call i32 @strlen(ptr noundef nonnull dereferenceable(1) [[HELLO_P]])
; CHECK-NEXT:    ret i32 [[HELLO_L]]
;
  %and = and i32 %x, 15
  %hello_p = getelementptr inbounds [13 x i8], ptr @null_hello_mid, i32 0, i32 %and
  %hello_l = call i32 @strlen(ptr %hello_p)
  ret i32 %hello_l
}

define i32 @test_no_simplify3_on_null_opt(i32 %x) #0 {
; CHECK-LABEL: @test_no_simplify3_on_null_opt(
; CHECK-NEXT:    [[AND:%.*]] = and i32 [[X:%.*]], 15
; CHECK-NEXT:    [[HELLO_P:%.*]] = getelementptr inbounds nuw [13 x i8], ptr @null_hello_mid, i32 0, i32 [[AND]]
; CHECK-NEXT:    [[HELLO_L:%.*]] = call i32 @strlen(ptr noundef nonnull dereferenceable(1) [[HELLO_P]])
; CHECK-NEXT:    ret i32 [[HELLO_L]]
;
  %and = and i32 %x, 15
  %hello_p = getelementptr inbounds [13 x i8], ptr @null_hello_mid, i32 0, i32 %and
  %hello_l = call i32 @strlen(ptr %hello_p)
  ret i32 %hello_l
}

define i32 @test1(ptr %str) {
; CHECK-LABEL: @test1(
; CHECK-NEXT:    [[LEN:%.*]] = tail call i32 @strlen(ptr noundef nonnull dereferenceable(1) [[STR:%.*]]) #[[ATTR1:[0-9]+]]
; CHECK-NEXT:    ret i32 [[LEN]]
;
  %len = tail call i32 @strlen(ptr %str) nounwind
  ret i32 %len
}

define i32 @test2(ptr %str) #0 {
; CHECK-LABEL: @test2(
; CHECK-NEXT:    [[LEN:%.*]] = tail call i32 @strlen(ptr noundef [[STR:%.*]]) #[[ATTR1]]
; CHECK-NEXT:    ret i32 [[LEN]]
;
  %len = tail call i32 @strlen(ptr %str) nounwind
  ret i32 %len
}

; Test cases for PR47149.
define i1 @strlen0_after_write_to_first_byte_global() {
; CHECK-LABEL: @strlen0_after_write_to_first_byte_global(
; CHECK-NEXT:    store i8 49, ptr @a, align 16
; CHECK-NEXT:    ret i1 false
;
  store i8 49, ptr @a, align 16
  %len = tail call i32 @strlen(ptr nonnull dereferenceable(1) @a)
  %cmp = icmp eq i32 %len, 0
  ret i1 %cmp
}

define i1 @strlen0_after_write_to_second_byte_global() {
; CHECK-LABEL: @strlen0_after_write_to_second_byte_global(
; CHECK-NEXT:    store i8 49, ptr getelementptr inbounds nuw (i8, ptr @a, i32 1), align 16
; CHECK-NEXT:    [[CHAR0:%.*]] = load i8, ptr @a, align 1
; CHECK-NEXT:    [[CMP:%.*]] = icmp eq i8 [[CHAR0]], 0
; CHECK-NEXT:    ret i1 [[CMP]]
;
  store i8 49, ptr getelementptr inbounds ([32 x i8], ptr @a, i64 0, i64 1), align 16
  %len = tail call i32 @strlen(ptr nonnull dereferenceable(1) @a)
  %cmp = icmp eq i32 %len, 0
  ret i1 %cmp
}

define i1 @strlen0_after_write_to_first_byte(ptr %ptr) {
; CHECK-LABEL: @strlen0_after_write_to_first_byte(
; CHECK-NEXT:    store i8 49, ptr [[PTR:%.*]], align 1
; CHECK-NEXT:    ret i1 false
;
  store i8 49, ptr %ptr
  %len = tail call i32 @strlen(ptr nonnull dereferenceable(1) %ptr)
  %cmp = icmp eq i32 %len, 0
  ret i1 %cmp
}

define i1 @strlen0_after_write_to_second_byte(ptr %ptr) {
; CHECK-LABEL: @strlen0_after_write_to_second_byte(
; CHECK-NEXT:    [[GEP:%.*]] = getelementptr i8, ptr [[PTR:%.*]], i32 1
; CHECK-NEXT:    store i8 49, ptr [[GEP]], align 1
; CHECK-NEXT:    [[CHAR0:%.*]] = load i8, ptr [[PTR]], align 1
; CHECK-NEXT:    [[CMP:%.*]] = icmp eq i8 [[CHAR0]], 0
; CHECK-NEXT:    ret i1 [[CMP]]
;
  %gep = getelementptr i8, ptr %ptr, i64 1
  store i8 49, ptr %gep
  %len = tail call i32 @strlen(ptr nonnull dereferenceable(1) %ptr)
  %cmp = icmp eq i32 %len, 0
  ret i1 %cmp
}

attributes #0 = { null_pointer_is_valid }

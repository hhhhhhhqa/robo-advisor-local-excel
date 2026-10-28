// Rebuild only VBA source; Excel compiles it for the recipient's Office version.
package main

import (
    "bytes"
    "fmt"
    "os"
    "path/filepath"
    "strings"
    "github.com/kay-ws/ovba-writer/vbaproject"
    "github.com/kay-ws/ovba-writer/cfb"
    "github.com/kay-ws/ovba-writer/ovba"
)

func main() {
    if len(os.Args) != 4 { panic("expected input.bin source-directory output.bin") }
    input, err := os.ReadFile(os.Args[1]); check(err)
    input = normalizeASCIIProject(input)
    project, err := vbaproject.Read(input); check(err)
    for i := range project.Modules {
        m := &project.Modules[i]
        var sourceName string
        if m.Name == "Module1" { sourceName = "Module1.bas" }
        if m.Name == "ThisWorkbook" { sourceName = "ThisWorkbook.cls" }
        if sourceName == "" { continue }
        source, err := os.ReadFile(filepath.Join(os.Args[2], sourceName)); check(err)
        disk := string(source)
        if m.Type == vbaproject.ModuleDocument {
            lines := strings.Split(disk, "\n")
            for len(lines) > 0 && strings.HasPrefix(lines[0], "Attribute ") { lines = lines[1:] }
            disk = strings.Join(lines, "\n")
        }
        m.Source, err = vbaproject.NormalizeModuleSource(m.Type, disk, m); check(err)
        fmt.Println("Updated VBA source:", m.Name)
    }
    output, err := vbaproject.Write(project); check(err)
    check(os.WriteFile(os.Args[3], output, 0644))
}

func check(err error) { if err != nil { panic(err) } }

// Native Mac templates use Mac Roman. All template source is ASCII, so switching
// the declared codepage to Windows-1252 is lossless and portable. Refuse any
// non-ASCII module instead of guessing at its encoding.
func normalizeASCIIProject(input []byte) []byte {
    container, err := cfb.Open(input); check(err)
    dir, ok := container.Stream("VBA/dir"); if !ok { panic("missing dir") }
    plain, err := ovba.Decompress(dir); check(err)
    info := ovba.ParseDir(plain)
    if info.CodePage != 10000 { return input }
    for _, m := range info.Modules {
        raw, ok := container.Stream("VBA/" + m.StreamName); if !ok { panic("missing module") }
        source, err := ovba.Decompress(raw[m.Offset:]); check(err)
        for _, b := range source { if b > 127 { panic("Mac template contains non-ASCII source") } }
    }
    signature := []byte{3, 0, 2, 0, 0, 0, 0x10, 0x27}
    if bytes.Count(plain, signature) != 1 { panic("ambiguous codepage record") }
    plain = bytes.Replace(plain, signature, []byte{3, 0, 2, 0, 0, 0, 0xe4, 4}, 1)
    dir, err = ovba.Compress(plain); check(err)
    writer := cfb.NewWriter()
    for _, path := range container.Paths() {
        raw, _ := container.Stream(path)
        if path == "VBA/dir" { raw = dir }
        writer.AddStream(strings.Split(path, "/"), raw)
    }
    output, err := writer.Bytes(); check(err)
    return output
}

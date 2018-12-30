strs = {}

loop do
  print '> '
  STDOUT.flush
  cmd, *args = gets.split
  begin
    case cmd
    when 'disas'
      stridx = args[0].to_i
      puts RubyVM::InstructionSequence::load_from_binary(strs[stridx]).disasm
    when 'gc'
      GC.start
    when 'write'
      stridx, i, c = args.map(&:to_i)
      (strs[stridx] ||= "\0"*(i + 1))[i] = c.chr
    when 'delete'
      stridx = args[0].to_i
      strs.delete stridx
    else
      puts "Unknown command"
    end
    STDOUT.flush
  rescue => e
    puts "Error: #{e}"
  end
end
